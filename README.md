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

Every stage's output passes through **ved-guardrail-agent** (line-by-line source check) before it moves on.
All stages share one tracker (a Claude Sheets workbook: Job Tracker, Interview Priority, Scoring Rules tabs).

## LangGraph runtime (`ved/`)

The pipeline is also implemented as a [LangGraph](https://github.com/langchain-ai/langgraph) `StateGraph`, so runs
are stateful, resumable and testable outside Claude.

```
preflight → source_score → tailor_cvs → guardrail_cvs ─┬─ live ──► gate_a ⏸ → apply → outreach → guardrail_emails → gate_b ⏸ ─┐
                                                       └─ scheduled ────────────────────────────────────────────────────────────┤
report ◄── book ◄── gate_c ⏸ ◄── live ── schedule ◄── triage ◄──────────────────────────────────────────────────────────────────┘
   ▲                                   └── scheduled ──► report            (status mode: preflight → report)
```

- **Gates** pause with `interrupt()` and resume with `Command(resume=<decision>)`. A checkpointer (SQLite in the
  CLI) keeps state between pause and resume, so a run can be picked up later.
- **State machine** (`ved/state.py`): every status change goes through `tracker.move()`, which rejects illegal
  moves (e.g. `Shortlisted → Applied` without approval) and writes an audit line.
- **Guardrail nodes** (`ved/guardrail.py`) check every CV and email line against the Master CV and JD: numbers
  not in the source and overstatement phrases are removed; any pay/CTC mention blocks the draft for Ritika.
- **Adapters** (`ved/adapters.py`): the graph only calls interfaces. Offline defaults run from fixture files;
  apply and send are *unavailable by default* and report "blocked" instead of pretending. Plug in real
  adapters (browser, Gmail, Calendar, Firecrawl) to go live.
- **Limits**: 5 CVs per run, 3 applications and 2 outreach emails per company.

```bash
pip install -e ".[dev]"
python -m pytest -q                                   # 8 tests: scoring, tracker, guardrail, all gates, CLI resume
python -m ved run --mode live --thread 2026-11-16 \
  --jobs examples/jobs.json --master-cv examples/master_cv.md
# ⏸ Paused at gate A … then:
python -m ved resume --thread 2026-11-16 --master-cv examples/master_cv.md \
  --decision '{"approve": ["<job id>"], "decline": {"<job id>": "reason"}}'
```

Gate decisions: A `{"approve": [...], "decline": {id: reason}}` · B `{"send": [...]}` · C `{"slots": {id: "slot"}}`.

## Repo layout

| Path | What it is |
|---|---|
| `ved/` | LangGraph implementation: state, graph, guardrail, scoring, tracker, adapters, CLI |
| `tests/` | pytest suite for the graph |
| `examples/` | Made-up jobs and a placeholder master CV for running the graph offline |
| `skills/job-pipeline-orchestrator/` | **VED**, the orchestrator: stages, state machine, approval gates, run modes |
| `skills/job-hunt-agent/` | Searches company boards and job sites, scores each JD 0–100 against the CV, shortlists, applies with approval |
| `skills/cv-maker-agent/` | Tailors an ATS-friendly CV per JD from a master CV, with a truth check and a match report |
| `skills/hr-outreach-scheduler-agent/` | Recruiter outreach, inbox triage, interview scheduling, colour-coded interview priority |
| `skills/ved-guardrail-agent/` | Guardrail and hallucination checker: verifies every CV line, tracker row, email and code change against its source before it passes a gate |
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

- Truthful tailoring only: nothing is added to a CV that isn't in the master CV, and the guardrail agent checks every line.
- Existing CVs are reused (master CV and same/similar-role tailored CVs) instead of duplicated.
- Approval before every application, email and calendar change; scheduled runs never pass a gate.
- No current CTC disclosed without explicit approval.
- Max 5 tailored CVs, 3 applications per company and 2 outreach emails per company per run.

## Not in this repo

Personal data stays out: CVs and CV PDFs, contact details, current compensation, and the live tracker
data. `dashboard/sample_job_tracker.csv` contains made-up rows.
