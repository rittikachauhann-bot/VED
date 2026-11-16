import json
from pathlib import Path

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from ved import guardrail, scoring, tracker
from ved.adapters import Adapters, FixtureSource, OfflineCalendar, OfflineMailer, ReuseFirstCVMaker, ToolUnavailable
from ved.graph import build_graph

EX = Path(__file__).resolve().parent.parent / "examples"
MASTER = (EX / "master_cv.md").read_text()


class FakeApplier:
    def __init__(self):
        self.applied = []

    def apply(self, job):
        self.applied.append(job["company"])


class SendingMailer(OfflineMailer):
    def __init__(self, inbox):
        super().__init__(None)
        self.inbox, self.sent = inbox, []

    def send(self, draft):
        self.sent.append(draft["job_id"])

    def job_emails(self):
        return self.inbox


def make(tmp_path, applier=None, mailer=None, master=MASTER):
    cal = OfflineCalendar()
    ad = Adapters(FixtureSource(EX / "jobs.json"), ReuseFirstCVMaker(tmp_path / "cvs"),
                  applier or FakeApplier(), mailer or OfflineMailer(), cal, master,
                  company_tiers={"Example Bank": 0.9})
    return build_graph(ad, MemorySaver()), ad, cal


def test_scoring_bands():
    assert scoring.job_score({"role_fit": 1, "skills": 1, "domain": 1, "seniority": 1, "feasibility": 1}) == 100
    assert [scoring.job_status(s) for s in (70, 69, 55, 54)] == ["Shortlisted", "Maybe", "Maybe", "Skipped"]
    assert scoring.interview_priority({"skills": 1, "company_tier": 1, "pay": 1})[1:3] == ("P1", "[P1 🟢]")
    with pytest.raises(KeyError):
        scoring.job_score({"vibes": 1})


def test_tracker_dedupes_and_blocks_illegal_moves():
    jobs, added = tracker.merge_new([], [{"company": "A", "title": "PM", "location": "X", "job_url": "u"}])
    jobs, added2 = tracker.merge_new(jobs, [{"company": "a", "title": "pm", "location": "x", "job_url": "v"}])
    assert len(jobs) == 1 and not added2
    with pytest.raises(ValueError):
        tracker.move(jobs[0], "Applied")


def test_guardrail_flags_unsupported_lines():
    text = "Owns the product roadmap\nDrove adoption across 40% of branches\nCurrent CTC 23.2 LPA"
    r = guardrail.check_text(text, MASTER)
    assert len(r.findings) == 2 and r.fixed == 1 and r.verdict == "blocked"
    assert "Drove adoption" not in r.text
    assert guardrail.check_text("Leads agile delivery with SAFe practices", MASTER).verdict == "pass"


def test_full_live_run_with_all_three_gates(tmp_path):
    inbox = []
    mailer = SendingMailer(inbox)
    app, ad, cal = make(tmp_path, mailer=mailer)
    cfg = {"configurable": {"thread_id": "t1"}}

    r = app.invoke({"mode": "live", "jobs": [], "run_date": "2026-11-16"}, cfg)
    gate = r["__interrupt__"][0].value
    assert gate["gate"] == "A"
    ids = [i["id"] for i in gate["items"]]
    assert len(ids) == 2  # data analyst role was skipped

    r = app.invoke(Command(resume={"approve": ids[:1], "decline": {ids[1]: "not now"}}), cfg)
    assert r["__interrupt__"][0].value["gate"] == "B"
    assert ad.applier.applied == ["Example Bank"]

    inbox.append({"job_id": ids[0], "kind": "interview", "round": "Hiring manager",
                  "fit": {"skills": 0.9, "pay": 0.8, "feasibility": 0.8, "stage": 0.6}})
    r = app.invoke(Command(resume={"send": ids[:1]}), cfg)
    gate_c = r["__interrupt__"][0].value
    assert gate_c["gate"] == "C" and gate_c["items"][0]["priority"] == "P1"

    r = app.invoke(Command(resume={"slots": {ids[0]: "Wed 15:30 IST"}}), cfg)
    statuses = {j["company"]: j["status"] for j in r["jobs"]}
    assert statuses == {"Example Bank": "Interview", "Example Cloud": "Shortlisted", "Example Retail": "Skipped"}
    assert cal.booked[0]["calendar_tag"] == "[P1 🟢]"
    assert mailer.sent == ids[:1]
    assert "Interview [P1 🟢] Example Bank" in r["report"]


def test_scheduled_run_never_applies_or_sends(tmp_path):
    app, ad, _ = make(tmp_path)
    r = app.invoke({"mode": "scheduled", "jobs": [], "run_date": "2026-11-16"},
                   {"configurable": {"thread_id": "t2"}})
    assert "__interrupt__" not in r
    assert ad.applier.applied == []
    assert "Waiting for Ritika (Gate A)" in r["report"]


def test_missing_tools_are_reported_not_faked(tmp_path):
    class NoBrowser:
        def apply(self, job):
            raise ToolUnavailable("browser not linked")

    app, _, _ = make(tmp_path, applier=NoBrowser())
    cfg = {"configurable": {"thread_id": "t3"}}
    r = app.invoke({"mode": "live", "jobs": [], "run_date": "2026-11-16"}, cfg)
    ids = [i["id"] for i in r["__interrupt__"][0].value["items"]]
    r = app.invoke(Command(resume={"approve": ids}), cfg)
    assert "__interrupt__" not in r  # nothing applied, so no emails to approve
    assert all(j["status"] != "Applied" for j in r["jobs"])
    assert "Blocked: S3: browser not linked" in r["report"]


def test_no_master_cv_blocks_tailoring(tmp_path):
    app, _, _ = make(tmp_path, master="")
    r = app.invoke({"mode": "scheduled", "jobs": []}, {"configurable": {"thread_id": "t4"}})
    assert "Blocked: S2 blocked: no Master CV" in r["report"]
    assert not any(j["status"] == "CV ready" for j in r["jobs"])


def test_cli_pause_and_resume_across_processes(tmp_path, capsys):
    from ved.__main__ import main
    common = ["--tracker", str(tmp_path / "t.csv"), "--jobs", str(EX / "jobs.json"),
              "--master-cv", str(EX / "master_cv.md"), "--cv-dir", str(tmp_path / "cvs"),
              "--db", str(tmp_path / "db.sqlite"), "--thread", "cli"]
    main(["run", *common])
    out = capsys.readouterr().out
    assert "Paused at gate A" in out
    first_id = json.loads(out[out.index("["):out.index("\nResume")])[0]["id"]
    main(["resume", *common, "--decision", json.dumps({"approve": [first_id]})])
    out = capsys.readouterr().out
    assert "Blocked: S3: browser not linked" in out
    rows = tracker.load(tmp_path / "t.csv")
    assert {r["status"] for r in rows} == {"Approved to apply", "CV ready", "Skipped"}
