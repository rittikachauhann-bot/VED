---
name: "job-pipeline-orchestrator"
description: "Run Ritika's whole job-search pipeline end to end: job-hunt-agent, cv-maker-agent and hr-outreach-scheduler-agent around one shared tracker, with approval gates. Use for \"run my job pipeline\", a daily job-search run, or a pipeline status check."
---

# VED — Job Pipeline Orchestrator

**VED** is the name of this pipeline. "Run VED", "VED status", "VED, just find jobs" and similar all mean this skill.

Connects Ritika's four agents (job-hunt-agent, cv-maker-agent, hr-outreach-scheduler-agent and the ved-guardrail-agent checker) into one pipeline. The orchestrator doesn't redo their work: it decides which stage runs, passes state between them through the tracker, and stops at every approval gate.

```
            ┌─────────────── SHARED STATE: "Interview Priority Ranking" workbook ───────────────┐
            │   Job Tracker tab  ·  Interview Priority tab  ·  Scoring Rules tab                     │
            └────────────────────────────────────────────────────────────────────────────┘
  S1 SOURCE & SCORE → S2 TAILOR CV → [GATE A: approve applications] → S3 APPLY → S4 OUTREACH
      job-hunt-agent     cv-maker-agent                                 job-hunt-agent   hr-outreach
  → [GATE B: approve emails] → S5 INBOX TRIAGE → S6 SCHEDULE + PRIORITISE → [GATE C: approve slots] → S7 REPORT
                                 hr-outreach         hr-outreach (section 5a)
```

## Shared state

- **Workbook:** the Sheets artifact **"Interview Priority Ranking"** (https://claude.ai/artifact/FLvbeSRfcqvQjRBCek1uKb). Read it with the Claude Docs connector (load the Sheets guide topics first).
  - **Job Tracker** tab: one row per job. Columns: `Score | Status | Company | Title | Location | Sponsorship | Match reason | Gaps | Pay range | Job URL | Date found | Tailored CV | Coverage % | Applied on | Recruiter | Outreach sent | Follow-up due | Notes`.
  - **Interview Priority** tab: one row per interview, scored by hr-outreach section 5a.
  - **Scoring Rules** tab: the priority weights. Agents read it; they don't change it.
- **Status values (the state machine):** `New → Shortlisted / Maybe / Skipped → CV ready → Approved to apply → Applied → Outreach sent → Interview → Offer / Rejected / Withdrawn`. Each stage only picks up rows in its input status, and moves them on.
- **Never** create a second tracker; never delete rows (set `Skipped` or `Withdrawn` instead).

## Pre-flight (every run)

Check silently and list anything missing in the report; run every stage that isn't blocked.

| Needed for | Check |
|---|---|
| S1 | Firecrawl jobs search and Indeed tools load. |
| S2 | The Master CV doc "Ritika Chouhan – AI Product Owner CV" can be read. If not, S2 is blocked: ask for the CV. |
| S3 | A browser is available (load its skill), and tailored CV files exist. |
| S4–S5 | The Gmail connector can search, draft and send. If not, suggest reconnecting it. |
| S6 | The Google Calendar connector is enabled. |

## Stages

**S1. Source & score** (job-hunt-agent, steps 1–4). Search the six target companies' boards plus Indeed for US/UK/India; read each JD; score it; add new rows (de-duplicated by URL and by company + title + location) with status `Shortlisted` (≥70), `Maybe` (55–69) or `Skipped`. Also check that existing open rows are still live (Firecrawl `urls` check); set closed ones to `Withdrawn` with Notes "posting closed".

**S2. Tailor CVs** (cv-maker-agent). For up to 5 `Shortlisted` rows without a CV, highest score first: reuse an existing tailored CV for the same or a similar role where one exists (never duplicate), otherwise build one from the Master CV; write the CV link and coverage % to the row.

**Guardrail checkpoint** (ved-guardrail-agent). After S1, check every new tracker row against its posting. After S2, check every line of every new or changed CV against the Master CV. Only rows whose CV passes move to `CV ready`; anything unresolved is flagged `[confirm?]` in Notes and listed in the report. The same checkpoint runs before Gates A, B and C and before any commit or published page.

**Gate A: approve applications.** Show the `CV ready` rows (company, title, score, coverage, the 3 biggest CV changes). Ritika approves rows by name or number → status `Approved to apply`. Rows she declines go back to `Shortlisted` with her reason in Notes.

**S3. Apply** (job-hunt-agent, step 6). Only `Approved to apply` rows. Follow its hand-back rules (sign-ins, CAPTCHAs, salary and EEO fields) and confirm before each Submit → status `Applied`, date in `Applied on`.

**S4. Outreach** (hr-outreach-scheduler-agent, step 3). For `Applied` rows with no outreach: find the recruiter, draft the email.

**Gate B: approve emails.** Show all drafts in one list; send only the ones approved → status `Outreach sent`, follow-up date = +7 business days.

**S5. Inbox triage** (hr-outreach step 4). Classify new job emails; draft replies; update statuses (`Interview`, `Rejected`, `Offer`); queue follow-ups that are due (back through Gate B).

**S6. Schedule & prioritise** (hr-outreach steps 5–5a). For each interview request: score it (section 5a), add it to the Interview Priority tab, and propose 3 slots in IST and the recruiter's time zone.

**Gate C: approve slots.** After Ritika picks, send the reply, then create the colour-coded calendar event (`[P1 🟢]` / `[P2 🟡]` / `[P3 🔴]`), the prep block and the prep brief.

**S7. Report** (always). One short summary, headed **"VED run – <date>"**, including the guardrail result (lines checked, issues fixed, items flagged):
- Pipeline counts by status (New / Shortlisted / CV ready / Applied / Interview / Offer / Rejected).
- Top new shortlisted roles (company, title, location, score, link).
- Waiting for Ritika: Gate A, B and C items, and anything blocked in pre-flight.
- Interviews this week, sorted by priority.
- The workbook link.

## Run modes

- **"Run my job pipeline"** (live): pre-flight, then S1 → S7, stopping at each gate and continuing once she answers.
- **Scheduled / unattended run:** S1, S2, S5, S6 (scoring and proposing slots only) and S7. Gates are never passed without her, so nothing is applied for, sent or booked. Put the gate items at the top of the report.
- **"Pipeline status"**: S7 only.
- **Single stage** ("just find jobs", "just triage my inbox"): run that stage and S7.

## Guardrails

- The agents' own rules still apply in full (truthful CVs, approval before any submission, email or calendar change, no CTC disclosure without her OK).
- Nothing passes a gate, gets sent or gets committed without a PASS from ved-guardrail-agent.
- Per run: at most 5 new tailored CVs, 3 applications per company, 2 outreach emails per company.
- If a stage fails (tool error after one retry, sign-in needed), mark it in the report and move on to the next stage that doesn't depend on it.