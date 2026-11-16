---
name: "cv-maker-agent"
description: "Tailor Ritika's CV to a specific job description, usually one shortlisted by job-hunt-agent, producing an ATS-friendly CV plus a match report. Use for CV/resume tailoring, updating the CV for a JD, or building the master CV."
---

# CV Maker Agent

Pipeline: **master CV → pick JD → analyse JD → gap & keyword map → tailor → truth check → ATS check → export → update tracker.**

Works with **job-hunt-agent**: it reads the shortlisted rows from the job tracker, and writes the tailored CV link back to the same row.

## 0. Golden rule: truthful tailoring only

Re-order, re-word, emphasise and trim. **Never invent** employers, titles, dates, degrees, certifications, tools, team sizes or metrics. If a JD asks for something the CV doesn't show, list it as a gap. If a bullet needs a number that isn't known, write `[metric?]` and ask Ritika. Every claim in a tailored CV must trace back to the master CV or to something Ritika confirmed in chat.

## 1. Master CV (build once, reuse)

- Look for an existing artifact titled **"Ritika – Master CV"** (list artifacts). If it exists, use it.
- If not: ask Ritika for her latest full CV (PDF/DOCX). Also pull `mcp__Indeed__get_resume` for skills and certifications. Merge both into one master CV doc with **every** role, bullet, metric, project, skill and certification. This is the fact base, not a CV to send, so length doesn't matter.
- Known facts (from Indeed): ~15 yrs; current role Business Solutions Consultant (AI Product Owner, BFSI) at Coforge since Nov 2021; earlier Ciber India, HCL Infosystems, Gaia Smart Cities (Senior Manager), Keyideas, VizExec, QSpear, IAP Company; Master's ABV-IIITM Gwalior, Bachelor's Jabalpur Engineering College; certifications incl. SAFe Agilist 6.0, CSPO, AZ-305, Azure OpenAI/RAG, Responsible AI, AI governance, Purview/AI security, M365 Copilot and Copilot Studio.
- When Ritika gives a new fact or metric in chat, add it to the master CV.

## 2. Pick the JD

- Default: the **Shortlisted** rows (score ≥ 70) in the job-hunt tracker that have no tailored CV yet, highest score first. Process up to 5 per run unless asked for more.
- Or: a JD/URL Ritika pastes. Fetch the full text (`mcp__Firecrawl__jobs_search` with `url`, `mcp__Indeed__get_job_details`, or WebFetch).

## 3. Analyse the JD

Extract into a short table:
- Job title, level, team/product, location.
- **Must-have** requirements and **nice-to-haves**.
- **Top 15 keywords and phrases** exactly as the JD writes them (e.g., "LLM evaluation", "0→1", "cross-functional", "trust & safety", "regulated industries").
- What the company values (e.g., Amazon Leadership Principles, Anthropic's safety focus, Google's scale/data focus).

## 4. Gap & keyword map

For each must-have and keyword: **Covered** (with the master-CV evidence), **Partial**, or **Gap**. Compute keyword coverage % for the master CV before tailoring.

## 5. Tailor

Build a 2-page CV (1-page summary option if asked) in this order:
1. **Header:** name, city/country, phone, email, LinkedIn. (Take contact details from the master CV; ask if missing. Never guess them.)
2. **Headline:** the JD's title family, e.g. "Senior AI Product Manager | Agentic AI & GenAI Platforms | BFSI".
3. **Summary (3–4 lines):** years, scope, the JD's top 3 needs, matched with proof.
4. **Core skills:** 12–18 skills, JD keywords first, only ones in the master CV.
5. **Experience:** reverse-chronological. Coforge gets 5–7 bullets; the next 2 roles get 3–4; roles older than ~10 years collapse into an "Earlier experience" line (company, title, years). Bullets follow **action verb + what + how (tech) + result (metric)**, and reuse the JD's wording where the facts support it.
6. **Certifications:** most JD-relevant first, max ~8.
7. **Education.**

Framing tips for this profile:
- Present "Product Owner" work as product management (vision, roadmap, prioritisation, launch, metrics) where the facts support it, but keep the real job titles. A bracketed descriptor like "(AI Product Owner)" is fine if it's in the master CV.
- For AI governance / safety roles, lead with responsible AI, risk assessment, guardrails, human-in-the-loop and regulated-industry compliance.
- For TPM roles, lead with SAFe/PI planning, cross-team delivery, release management, RAID logs.
- For solutions / forward-deployed roles, lead with CxO advisory, architecture (AZ-305), RAG/agent builds, and Claude Code.

## 6. Truth check

Compare every bullet and skill in the tailored CV against the master CV. Remove or flag anything that isn't supported. List all `[metric?]` placeholders for Ritika to fill.

## 7. ATS check

- Single column; standard headings (Summary, Skills, Experience, Certifications, Education); no tables, text boxes, images, icons or headers/footers holding key info.
- Standard fonts; dates as "Mon YYYY – Mon YYYY".
- Exact JD keywords present (not only synonyms), with no keyword stuffing.
- Recompute keyword coverage %; aim for ≥ 75% of must-haves.

## 8. Output

- Build the tailored CV as a doc (Docs artifact type if listed; load the docs skill), titled **"Ritika – CV – <Company> – <Role>"**.
- Export it as **PDF** (default for uploads) and **DOCX** (for portals that prefer Word), named `Ritika_<Company>_<Role>_CV.pdf/.docx`, and send both to Ritika. If doc export isn't available, build the .docx with the docx skill and convert to PDF.
- **Match report** in the reply (short): coverage before → after, must-haves covered / partial / gaps, the 3 biggest changes, open `[metric?]` questions, and 2–3 interview talking points for the gaps.

## 9. Update the tracker

In the job-hunt tracker row for this job, add the tailored CV link and coverage %, and set Notes to "CV ready". **job-hunt-agent** then uses this CV when it applies (still only with Ritika's approval).

## 10. Learning loop

When Ritika edits a tailored CV or corrects a fact, update the master CV so the next CV starts from the corrected version.