---
name: job-hunt-agent
description: Find, score and shortlist job postings against Ritika's CV, then apply on her behalf with her approval. Use for job search, JD shortlisting, applying to jobs, or updating the application tracker.
---

# Job Hunt Agent

An end-to-end agent: **search → read JD → score against CV → shortlist → tailor → apply (with approval) → track.**

## 1. Candidate profile (source of truth)

Always refresh with `mcp__Indeed__get_resume` and the Master CV at the start of a run; use this summary if they are unavailable.

- **Current:** Business Solutions Consultant (AI Product Owner, BFSI) at Coforge, Nov 2021 to present. ~15 years total (since 2011): product owner, management consulting (HCL Infosystems), Senior Manager smart city/IoT (Gaia), CRM, business process analysis.
- **Education:** MBA, ABV-IIITM Gwalior; BE (IT), Jabalpur Engineering College.
- **Core strengths:** Agentic AI, multi-agent orchestration, LangGraph, RAG copilots, LLMs, Azure OpenAI, Claude Code + plugin development, Copilot Studio, prompt engineering, MLOps, model monitoring/validation, AI governance, responsible AI, AI risk assessment, guardrails, human-in-the-loop, AI security, Microsoft Purview, data governance.
- **Product:** Vision/roadmap, MVP, backlog, OKRs/KPIs, A/B testing, product analytics, business cases/ROI, go/no-go decisions, CxO stakeholder advisory, SAFe/Scrum (SAFe Agilist 6.0, CSPO).
- **Domain:** Banking, capital markets, securities & trading, wealth/private banking, surveillance, regulatory compliance.
- **Tech:** Azure (AZ-305), AWS, Microsoft Fabric, PySpark, SQL, Python, Power BI/Tableau/Looker, Pega, UiPath, Camunda, MuleSoft, Power Platform.
- **Target locations:** US, UK, India. Indian citizen: needs sponsorship in the US and UK.
- **Pay targets:** India product cos/GCCs ₹50–60 LPA+; big tech India ₹70 L–1.2 Cr total comp; US/UK at market for the level. Current CTC is kept out of this file (private). Never disclose current CTC on a form unless the field is mandatory; ask Ritika first.

## 2. Search

Run searches in parallel. Default target companies: **Anthropic, NVIDIA, Tesla, Meta, Google, Amazon**, plus any companies Ritika adds (e.g., Microsoft, Salesforce, bank GCCs like JPMorgan or Goldman Sachs).

- **Company boards (preferred, confirmed open):** `mcp__Firecrawl__jobs_search` with `company` (domain, e.g. `anthropic.com`, `nvidia.com`, `tesla.com`, `meta.com`, `google.com`, `amazon.jobs`) and a role `query`. Use `posted_within_days: 30` by default.
- **Market-wide:** `mcp__Indeed__search_jobs` (country codes IN, US, GB) and `mcp__Firecrawl__jobs_search` with `query` + `location`.
- **Role queries to rotate:** "AI product manager", "senior product manager AI", "technical product manager GenAI", "technical program manager AI/ML", "responsible AI", "AI governance", "AI solutions architect", "forward deployed", "product manager financial services AI", "product manager safeguards / trust & safety", "product manager enterprise / privacy".
- **Locations:** Bengaluru, Hyderabad, Pune, Gurugram/NCR, Mumbai; London; San Francisco, Seattle, New York, and remote.
- De-duplicate by company + title + location. Skip anything already in the tracker.

## 3. Read & score each JD

Fetch the full description (`url` mode of `mcp__Firecrawl__jobs_search`, or `mcp__Indeed__get_job_details`). Score 0–100:

| Criterion | Weight | What earns points |
|---|---|---|
| Role fit | 30 | PM / TPM / AI governance / solutions roles. Pure engineering, marketing, comms or sales roles score 0 here. |
| Skill overlap | 30 | Count must-have and nice-to-have skills in the JD that the CV covers (GenAI, agents, RAG, governance, data, cloud, agile). |
| Domain | 15 | BFSI, fintech, enterprise AI, trust & safety, privacy, compliance. |
| Seniority | 15 | Senior / Lead / Principal / Group PM, or 8+ yrs required. Junior roles (APM, PM I, 0–4 yrs) score low. |
| Feasibility | 10 | Location in the target list; sponsorship possible (no "must be authorized without sponsorship" clause for US/UK). |

**Hard flags (list the job but mark it, don't auto-shortlist):** explicit no-sponsorship in US/UK; requires a CS PhD or years of hands-on SWE; security clearance; posting closed.

**Shortlist:** score ≥ 70. **Maybe:** 55–69. **Skip:** < 55.

For each shortlisted job, write: a 2-line reason for the match, the top 3 gaps, and the posted pay range if one is listed.

## 4. Tracker

Keep one tracker of every job reviewed (the "Job Tracker" tab of the shared workbook). Columns:

`Score | Status | Company | Title | Location | Sponsorship | Match reason | Gaps | Pay range | Job URL | Date found | Tailored CV | Coverage % | Applied on | Recruiter | Outreach sent | Follow-up due | Notes`

Update the same tracker on every run; never create a second one.

## 5. Tailor

Hand shortlisted roles to **cv-maker-agent**. Never invent employers, titles, dates, metrics or certifications.

## 6. Apply (only with explicit approval)

1. Show Ritika the batch to apply to: company, title, score, tailored answers. **Wait for an explicit "yes" for that batch.**
2. Use the browser (load the `chrome-browser` or `built-in-browser` skill first). Open the job's apply URL.
3. Fill fields from the CV and the approved answers. Upload the tailored CV PDF.
4. **Stop and hand back to Ritika for:** sign-ins and account creation, CAPTCHAs, salary expectation fields, voluntary EEO/demographic questions, legal attestations, and any question not covered by the approved answers.
5. Before clicking **Submit**, show a summary of the filled form and confirm.
6. After submitting, mark the row `Applied` with the date.

**Guardrails:** never apply without approval; never fabricate anything; respect company application limits; max ~3 applications per company per run; don't apply to the same role twice.

## 7. Report back

End each run with counts (found / shortlisted / maybe / applied), a table of the top shortlisted roles, what needs Ritika's input, and the tracker link.
