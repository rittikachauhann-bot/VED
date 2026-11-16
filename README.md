# VED: agentic AI job-search pipeline

VED is an orchestrated set of Claude agents (packaged as Claude skills) that runs a job search end to end:
find and score roles, tailor a truthful CV for each, handle recruiter email and interview scheduling,
and report daily, with a human approval gate before anything is submitted, sent or booked.

```
 S1 SOURCE & SCORE ─► S2 TAILOR CV ─► [GATE A: approve applications] ─► S3 APPLY ─► S4 OUTREACH
   job-hunt-agent       cv-maker-agent                                    job-hunt-agent  hr-outreach
 ─► [GATE B: approve emails] ─► S5 INBOX TRIAGE ─► S6 SCHEDULE + PRIORITISE ─► [GATE C: approve slots] ─► S7 REPORT
                                  hr-outreach        hr-outreach (green/yellow/red priority)
```

All stages share one tracker (a Claude Sheets workbook: Job Tracker, Interview Priority, Scoring Rules tabs).

## Repo layout

| Path | What it is |
|---|---|
| `skills/job-pipeline-orchestrator/` | **VED**, the orchestrator: stages, state machine, approval gates, run modes |
| `skills/job-hunt-agent/` | Searches company boards and job sites, scores each JD 0–100 against the CV, shortlists, applies with approval |
| `skills/cv-maker-agent/` | Tailors an ATS-friendly CV per JD from a master CV, with a truth check and a match report |
| `skills/hr-outreach-scheduler-agent/` | Recruiter outreach, inbox triage, interview scheduling, colour-coded interview priority |
| `dashboard/` | Page and data schema for the pipeline dashboard (a Claude Data artifact) |
| `cv-downloads/` | Page that serves the tailored CV PDFs for download (PDFs are not committed) |
| `scheduled/` | The daily scheduled-run prompt |

## Interview priority (hr-outreach-scheduler-agent, section 5a)

| Factor | Weight |
|---|---|
| Skills match | 35 |
| Company tier | 25 |
| Pay vs target | 20 |
| Feasibility (location, visa) | 10 |
| Stage | 10 |

75+ = P1 🟢 Green (`colorId 10`), 55–74 = P2 🟡 Yellow (`5`), below 55 = P3 🔴 Red (`11`). Calendar titles carry a
`[P1 🟢]`-style tag so interviews can be filtered by searching `[P1`.

## Guardrails

- Truthful tailoring only: nothing is added to a CV that isn't in the master CV.
- Approval before every application, email and calendar change; scheduled runs never pass a gate.
- No current CTC disclosed without explicit approval.
- Max 5 tailored CVs, 3 applications per company and 2 outreach emails per company per run.

## Not in this repo

Personal data stays out: CVs and CV PDFs, contact details, current compensation, and the live tracker
data. `dashboard/sample_job_tracker.csv` contains made-up rows.
