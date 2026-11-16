# VED daily scheduled run

- **Schedule:** every day at 07:13 Asia/Calcutta (`CRON_TZ=Asia/Calcutta 13 7 * * *`)
- **Runs:** in the cloud, unattended. Push notification with the run summary.
- **Never** applies, sends emails, accepts invites or changes calendar events: those wait for approval in a live chat.

## Prompt sent on each run

```
Run VED, Ritika's job-search pipeline, as a scheduled unattended run. Load the skill
"job-pipeline-orchestrator" (VED) with the Skill tool and follow its "Scheduled / unattended run"
mode. It in turn uses the skills job-hunt-agent, cv-maker-agent and hr-outreach-scheduler-agent.

FIXED LOCATIONS (always reuse these; never create a second tracker or dashboard):
- Tracker workbook (Sheets artifact, edited via the Claude Docs connector): tabs "Job Tracker",
  "Interview Priority", "Scoring Rules".
- Master CV (fact base for tailoring, never invent beyond it).
- Dashboard (Data-type artifact).
- Application checklist sheet.
(Private artifact links are kept in the live scheduled task, not in this repo.)

WHAT TO DO THIS RUN:
1. S1 Source & score: search Anthropic, NVIDIA, Tesla, Meta, Google, Amazon plus market searches for
   US, UK and India, posted in the last 7 days. De-duplicate by Job URL and company+title+location.
   Score new roles (job-hunt-agent rubric) and append rows (Shortlisted >=70, Maybe 55-69,
   Skipped <55). Check open rows are still live; set closed ones to Withdrawn. Re-sort by Score.
2. S2 Tailor CVs: up to 5 Shortlisted rows without a CV -> cv-maker-agent -> Status "CV ready".
3. S5/S6: if Gmail can search, triage job emails and draft replies (never send). If Google Calendar
   is available, score interviews and add them to the Interview Priority tab; propose slots only.
4. Never apply, send, accept or change calendar events in this run.
5. Refresh the dashboard: export Job Tracker to CSV (schema in dashboard/README.md), upload it as an
   asset of the dashboard, and point datasets/tracker at the new /_blob/ url with updated.at = now.
6. Report: "VED run – <date>": new roles, CVs tailored, items waiting for approval, pipeline counts,
   anything blocked, and the dashboard and tracker links.
```
