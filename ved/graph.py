"""VED as a LangGraph StateGraph.

  preflight → source_score → tailor_cvs → guardrail_cvs ─┬─(live)──→ gate_a ⏸ → apply → outreach
                                                         │            → guardrail_emails → gate_b ⏸ ─┐
                                                         └─(scheduled)───────────────────────────────┤
                                                                                                      ↓
                                     report ← book ← gate_c ⏸ ←(live)── schedule ←────────────── triage
                                        ↑                               └─(scheduled)→ report
  status mode: preflight → report

Gates use langgraph.types.interrupt(): the run pauses with the gate items and resumes with
Command(resume=<Ritika's decision>). A checkpointer keeps the state between pause and resume.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from . import guardrail, scoring, tracker
from .adapters import Adapters, ToolUnavailable
from .state import MAX_APPS_PER_COMPANY, MAX_CVS_PER_RUN, MAX_OUTREACH_PER_COMPANY, VEDState


def _business_days(start: date, n: int) -> date:
    d = start
    while n:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n -= 1
    return d


def build_graph(ad: Adapters, checkpointer=None):
    def by_id(state: VEDState) -> dict:
        return {j["id"]: j for j in state.get("jobs", [])}

    # ---------- S0 pre-flight ----------
    def preflight(state: VEDState):
        blocked = []
        if not ad.master_cv.strip():
            blocked.append("S2 blocked: no Master CV")
        return {"blocked": blocked, "run_date": state.get("run_date") or date.today().isoformat()}

    # ---------- S1 source & score ----------
    def source_score(state: VEDState):
        try:
            found = ad.source.search()
        except ToolUnavailable as e:
            return {"blocked": [f"S1: {e}"]}
        for j in found:
            j["score"] = scoring.job_score(j.pop("fit", {}))
            j["date_found"] = state["run_date"]
        jobs, added = tracker.merge_new(state.get("jobs", []), found)
        events, out = [], []
        for j in jobs:
            if j["status"] == "New":
                j, ev = tracker.move(j, scoring.job_status(j["score"]))
                events.append(ev)
            out.append(j)
        return {"jobs": out, "events": [f"S1: {len(added)} new roles"] + events}

    # ---------- S2 tailor CVs (reuse first) ----------
    def tailor_cvs(state: VEDState):
        if not ad.master_cv.strip():
            return {}
        todo = sorted((j for j in state["jobs"] if j["status"] == "Shortlisted"),
                      key=lambda j: -j["score"])[:MAX_CVS_PER_RUN]
        jobs, drafts = by_id(state), []
        for j in todo:
            text, url, cov = ad.cv_maker.tailor(j, ad.master_cv)
            drafts.append({"job_id": j["id"], "kind": "cv", "body": text})
            jobs[j["id"]] = {**j, "cv_url": url, "coverage": cov}
        return {"jobs": list(jobs.values()), "drafts": drafts}

    # ---------- guardrail on CVs ----------
    def guardrail_cvs(state: VEDState):
        jobs, kept, log, events = by_id(state), [], [], []
        found = fixed = lines = 0
        needs = []
        for d in state.get("drafts", []):
            if d["kind"] != "cv":
                kept.append(d)
                continue
            j = jobs[d["job_id"]]
            r = guardrail.check_text(d["body"], ad.master_cv)
            lines += r.lines_checked
            found += len(r.findings)
            fixed += r.fixed
            if r.verdict == "blocked":
                needs += [f"{j['company']}: {f.line} ({f.reason})" for f in r.findings]
                continue
            jobs[j["id"]], ev = tracker.move(j, "CV ready", f"guardrail {r.verdict}")
            events.append(ev)
            kept.append({**d, "body": r.text, "guardrail": r.verdict})
        log.append({"area": "CVs", "items_checked": len([d for d in state.get("drafts", []) if d["kind"] == "cv"]),
                    "issues_found": found, "issues_fixed": fixed, "needs_ritika": needs})
        return {"jobs": list(jobs.values()), "drafts": kept, "guardrail_log": log, "events": events}

    # ---------- Gate A ----------
    def gate_a(state: VEDState):
        ready = [j for j in state["jobs"] if j["status"] == "CV ready"]
        if not ready:
            return {}
        decision = interrupt({"gate": "A", "question": "Approve these applications?",
                              "items": [{k: j.get(k) for k in ("id", "company", "title", "score", "coverage", "cv_url")}
                                        for j in ready]})
        approve = set(decision.get("approve", []))
        decline = decision.get("decline", {})
        jobs, events = by_id(state), []
        for j in ready:
            if j["id"] in approve:
                jobs[j["id"]], ev = tracker.move(j, "Approved to apply", "Approved by Ritika")
            elif j["id"] in decline:
                jobs[j["id"]], ev = tracker.move(j, "Shortlisted", f"Declined: {decline[j['id']]}")
            else:
                continue
            events.append(ev)
        return {"jobs": list(jobs.values()), "events": events}

    # ---------- S3 apply ----------
    def apply(state: VEDState):
        jobs, events, blocked = by_id(state), [], []
        per_company = Counter()
        for j in state["jobs"]:
            if j["status"] != "Approved to apply":
                continue
            if per_company[j["company"]] >= MAX_APPS_PER_COMPANY:
                events.append(f"{j['company']} – {j['title']}: held for next run (company limit)")
                continue
            try:
                ad.applier.apply(j)
            except ToolUnavailable as e:
                blocked.append(f"S3: {e}")
                break
            jobs[j["id"]], ev = tracker.move({**j, "applied_on": state["run_date"]}, "Applied")
            per_company[j["company"]] += 1
            events.append(ev)
        return {"jobs": list(jobs.values()), "events": events, "blocked": blocked}

    # ---------- S4 outreach drafts ----------
    def outreach(state: VEDState):
        done = {d["job_id"] for d in state.get("drafts", []) if d["kind"] == "email"}
        per_company = Counter()
        drafts = list(state.get("drafts", []))
        for j in state["jobs"]:
            if (j["status"] == "Applied" and j["id"] not in done
                    and per_company[j["company"]] < MAX_OUTREACH_PER_COMPANY):
                drafts.append(ad.mailer.draft_outreach(j))
                per_company[j["company"]] += 1
        return {"drafts": drafts}

    def guardrail_emails(state: VEDState):
        jobs, kept, needs = by_id(state), [], []
        found = fixed = n = 0
        for d in state.get("drafts", []):
            if d["kind"] != "email":
                kept.append(d)
                continue
            n += 1
            j = jobs[d["job_id"]]
            r = guardrail.check_text(d["body"], ad.master_cv + "\n" + j.get("jd_text", ""))
            found += len(r.findings)
            fixed += r.fixed
            if r.verdict == "blocked":
                needs += [f"{j['company']} email: {f.reason}" for f in r.findings]
                continue
            kept.append({**d, "body": r.text, "guardrail": r.verdict})
        return {"drafts": kept, "guardrail_log": [{"area": "Emails", "items_checked": n, "issues_found": found,
                                                   "issues_fixed": fixed, "needs_ritika": needs}]}

    # ---------- Gate B ----------
    def gate_b(state: VEDState):
        emails = [d for d in state.get("drafts", []) if d["kind"] == "email"]
        if not emails:
            return {}
        decision = interrupt({"gate": "B", "question": "Send these emails?", "items": emails})
        send = set(decision.get("send", []))
        jobs, events, blocked, remaining = by_id(state), [], [], []
        for d in state["drafts"]:
            if d["kind"] != "email" or d["job_id"] not in send:
                remaining.append(d)
                continue
            try:
                ad.mailer.send(d)
            except ToolUnavailable as e:
                blocked.append(f"S4: {e}")
                remaining.append(d)
                continue
            j = jobs[d["job_id"]]
            due = _business_days(date.fromisoformat(state["run_date"]), 7).isoformat()
            jobs[j["id"]], ev = tracker.move({**j, "follow_up_due": due}, "Outreach sent")
            events.append(ev)
        return {"jobs": list(jobs.values()), "drafts": remaining, "events": events, "blocked": blocked}

    # ---------- S5 inbox triage ----------
    def triage(state: VEDState):
        try:
            emails = ad.mailer.job_emails()
        except ToolUnavailable as e:
            return {"blocked": [f"S5: {e}"]}
        jobs, events, interviews = by_id(state), [], list(state.get("interviews", []))
        target = {"interview": "Interview", "rejection": "Rejected", "offer": "Offer"}
        for e in emails:
            j = jobs.get(e["job_id"])
            if not j or e["kind"] not in target:
                continue
            if j["status"] != target[e["kind"]]:
                jobs[j["id"]], ev = tracker.move(j, target[e["kind"]])
                events.append(ev)
            if e["kind"] == "interview":
                interviews.append({"job_id": j["id"], "company": j["company"], "role": j["title"],
                                   "round": e.get("round", ""), "fit": e.get("fit", {})})
        return {"jobs": list(jobs.values()), "interviews": interviews, "events": events}

    # ---------- S6 schedule & prioritise ----------
    def schedule(state: VEDState):
        out = []
        for iv in state.get("interviews", []):
            if iv.get("priority"):
                out.append(iv)
                continue
            fit = dict(iv.pop("fit", {}))
            fit.setdefault("company_tier", ad.company_tiers.get(iv["company"], 0.5))
            score, p, tag, _ = scoring.interview_priority(fit)
            out.append({**iv, "score": score, "priority": p, "calendar_tag": tag,
                        "proposed_slots": ad.calendar.propose_slots(iv)})
        return {"interviews": sorted(out, key=lambda i: -i["score"])}

    # ---------- Gate C + booking ----------
    def gate_c(state: VEDState):
        open_ = [i for i in state.get("interviews", []) if not i.get("chosen_slot")]
        if not open_:
            return {}
        decision = interrupt({"gate": "C", "question": "Pick a slot for each interview",
                              "items": [{k: i.get(k) for k in ("job_id", "company", "role", "priority",
                                                                "calendar_tag", "proposed_slots")} for i in open_]})
        slots = decision.get("slots", {})
        return {"interviews": [{**i, "chosen_slot": slots[i["job_id"]]} if i["job_id"] in slots else i
                               for i in state["interviews"]]}

    def book(state: VEDState):
        events, out = [], []
        for i in state.get("interviews", []):
            if i.get("chosen_slot") and not i.get("booked"):
                ad.calendar.book(i)
                i = {**i, "booked": True}
                events.append(f"Booked {i['calendar_tag']} {i['company']} – {i['role']} at {i['chosen_slot']}")
            out.append(i)
        return {"interviews": out, "events": events}

    # ---------- S7 report ----------
    def report(state: VEDState):
        jobs = state.get("jobs", [])
        counts = Counter(j["status"] for j in jobs)
        lines = [f"VED report – {state.get('run_date')} ({state.get('mode')})",
                 "Pipeline: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items()))]
        waiting = [j for j in jobs if j["status"] == "CV ready"]
        if waiting:
            lines.append("Waiting for Ritika (Gate A): " + "; ".join(f"{j['company']} – {j['title']} ({j['score']})"
                                                                     for j in waiting))
        top = sorted((j for j in jobs if j["status"] in {"Shortlisted", "CV ready"}), key=lambda j: -j["score"])[:5]
        if top:
            lines.append("Top roles: " + "; ".join(f"{j['company']} – {j['title']} ({j['score']})" for j in top))
        for i in state.get("interviews", []):
            lines.append(f"Interview {i.get('calendar_tag')} {i['company']} – {i['role']}")
        for g in state.get("guardrail_log", []):
            lines.append(f"Guardrail {g['area']}: {g['issues_found']} found, {g['issues_fixed']} fixed"
                         + (f", {len(g['needs_ritika'])} need Ritika" if g["needs_ritika"] else ""))
        for b in dict.fromkeys(state.get("blocked", [])):
            lines.append(f"Blocked: {b}")
        return {"report": "\n".join(lines)}

    # ---------- wiring ----------
    g = StateGraph(VEDState)
    for name, fn in [("preflight", preflight), ("source_score", source_score), ("tailor_cvs", tailor_cvs),
                     ("guardrail_cvs", guardrail_cvs), ("gate_a", gate_a), ("apply", apply),
                     ("outreach", outreach), ("guardrail_emails", guardrail_emails), ("gate_b", gate_b),
                     ("triage", triage), ("schedule", schedule), ("gate_c", gate_c), ("book", book),
                     ("report", report)]:
        g.add_node(name, fn)

    live = lambda s: s.get("mode", "live") == "live"  # noqa: E731
    g.add_edge(START, "preflight")
    g.add_conditional_edges("preflight", lambda s: "report" if s.get("mode") == "status" else "source_score",
                            ["report", "source_score"])
    g.add_edge("source_score", "tailor_cvs")
    g.add_edge("tailor_cvs", "guardrail_cvs")
    g.add_conditional_edges("guardrail_cvs", lambda s: "gate_a" if live(s) else "triage", ["gate_a", "triage"])
    g.add_edge("gate_a", "apply")
    g.add_edge("apply", "outreach")
    g.add_edge("outreach", "guardrail_emails")
    g.add_edge("guardrail_emails", "gate_b")
    g.add_edge("gate_b", "triage")
    g.add_edge("triage", "schedule")
    g.add_conditional_edges("schedule", lambda s: "gate_c" if live(s) else "report", ["gate_c", "report"])
    g.add_edge("gate_c", "book")
    g.add_edge("book", "report")
    g.add_edge("report", END)
    return g.compile(checkpointer=checkpointer)
