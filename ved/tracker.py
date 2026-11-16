"""CSV-backed tracker that mirrors the Job Tracker tab (same columns as the dashboard's job_tracker.csv)."""
from __future__ import annotations

import csv
import hashlib
from pathlib import Path

from .state import TRANSITIONS, Job

COLUMNS = ["score", "status", "company", "title", "location", "sponsorship", "pay_range",
           "job_url", "date_found", "cv_url", "coverage", "applied_on", "follow_up_due", "notes"]


def job_id(job: Job) -> str:
    key = job.get("job_url") or f"{job.get('company')}|{job.get('title')}|{job.get('location')}"
    return hashlib.sha1(key.lower().encode()).hexdigest()[:10]


def load(path: str | Path) -> list[Job]:
    p = Path(path)
    if not p.exists():
        return []
    with p.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    jobs: list[Job] = []
    for r in rows:
        j: Job = {k: r.get(k, "") for k in COLUMNS}  # type: ignore[assignment]
        j["score"] = int(r["score"]) if r.get("score") else 0
        j["coverage"] = int(r["coverage"]) if r.get("coverage") else 0
        j["id"] = job_id(j)
        jobs.append(j)
    return jobs


def save(path: str | Path, jobs: list[Job]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        w.writeheader()
        for j in jobs:
            w.writerow({k: j.get(k, "") for k in COLUMNS})


def merge_new(jobs: list[Job], found: list[Job]) -> tuple[list[Job], list[Job]]:
    """Add found jobs that aren't already tracked (by URL, or company+title+location). Never deletes."""
    seen_urls = {j.get("job_url", "").lower() for j in jobs if j.get("job_url")}
    seen_keys = {(j.get("company", "").lower(), j.get("title", "").lower(), j.get("location", "").lower())
                 for j in jobs}
    added: list[Job] = []
    for j in found:
        key = (j.get("company", "").lower(), j.get("title", "").lower(), j.get("location", "").lower())
        if (j.get("job_url") and j["job_url"].lower() in seen_urls) or key in seen_keys:
            continue
        j = {**j, "id": job_id(j), "status": j.get("status", "New")}
        added.append(j)
        seen_keys.add(key)
        if j.get("job_url"):
            seen_urls.add(j["job_url"].lower())
    return jobs + added, added


def move(job: Job, new_status: str, note: str = "") -> tuple[Job, str]:
    """Return a copy of the job in the new status, plus an audit line. Rejects illegal transitions."""
    old = job.get("status", "New")
    if new_status not in TRANSITIONS.get(old, set()):
        raise ValueError(f"illegal transition {old!r} -> {new_status!r} for {job.get('company')} {job.get('title')}")
    updated: Job = {**job, "status": new_status}
    if note:
        updated["notes"] = f"{job['notes']}; {note}" if job.get("notes") else note
    return updated, f"{job.get('company')} – {job.get('title')}: {old} → {new_status}" + (f" ({note})" if note else "")
