"""Pluggable adapters: the graph only talks to these interfaces.

In Claude, each one is backed by a connector or skill (Firecrawl/Indeed, Claude Docs, a browser,
Gmail, Google Calendar). Locally, the offline defaults below run the whole graph from fixture files
so the orchestration can be tested without touching anything real. Adapters that would act on
Ritika's behalf (apply, send, book) are unavailable by default and must be supplied explicitly.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from .state import Draft, Interview, Job


class ToolUnavailable(RuntimeError):
    """Raised when the tool a stage needs isn't connected; the stage is marked blocked."""


class JobSource(Protocol):
    def search(self) -> list[Job]:
        """Return candidate jobs. Each job carries a 'fit' dict of 0-1 parts for scoring."""


class CVMaker(Protocol):
    def tailor(self, job: Job, master_cv: str) -> tuple[str, str, int]:
        """Return (cv_text, cv_url, coverage_percent)."""


class Applier(Protocol):
    def apply(self, job: Job) -> None: ...


class Mailer(Protocol):
    def draft_outreach(self, job: Job) -> Draft: ...
    def send(self, draft: Draft) -> None: ...
    def job_emails(self) -> list[dict]:
        """New recruiter emails: {'job_id', 'kind': interview|rejection|offer, 'round', 'fit': {...}}."""


class Calendar(Protocol):
    def propose_slots(self, interview: Interview) -> list[str]: ...
    def book(self, interview: Interview) -> None: ...


# ---------- offline defaults ----------

@dataclass
class FixtureSource:
    path: Path

    def search(self) -> list[Job]:
        return json.loads(Path(self.path).read_text(encoding="utf-8"))


@dataclass
class ReuseFirstCVMaker:
    """Reuses an existing CV when the job already has one; otherwise builds a plain draft
    from Master CV lines that share words with the JD. Coverage = share of JD keywords covered."""
    out_dir: Path = Path("cvs")

    def tailor(self, job: Job, master_cv: str) -> tuple[str, str, int]:
        jd_words = {w for w in job.get("jd_text", "").lower().split() if len(w) > 4}
        lines = [ln for ln in master_cv.splitlines() if ln.strip()]
        picked = [ln for ln in lines if jd_words & set(ln.lower().split())] or lines[:8]
        covered = jd_words & set(" ".join(picked).lower().split())
        coverage = round(100 * len(covered) / len(jd_words)) if jd_words else 0
        if job.get("cv_url"):
            return "\n".join(picked), job["cv_url"], coverage
        self.out_dir.mkdir(parents=True, exist_ok=True)
        path = self.out_dir / f"{job['id']}.md"
        path.write_text(f"# Ritika Chouhan – {job.get('title')}\n\n" + "\n".join(picked), encoding="utf-8")
        return "\n".join(picked), str(path), coverage


class UnavailableApplier:
    def apply(self, job: Job) -> None:
        raise ToolUnavailable("browser not linked: can't submit applications")


@dataclass
class OfflineMailer:
    """Drafts emails locally; can't send. Reads triage input from an optional fixture."""
    inbox_fixture: Path | None = None

    def draft_outreach(self, job: Job) -> Draft:
        return {
            "job_id": job["id"], "kind": "email", "to": "",
            "subject": f"Application: {job.get('title')} – Ritika Chouhan",
            "body": (f"Hello,\n\nI've applied for the {job.get('title')} role at {job.get('company')} "
                     "and wanted to introduce myself. I'm a Senior AI Product Owner working on AI products "
                     "in banking and financial services.\n\nMy tailored CV is attached. "
                     "I'd welcome a short conversation.\n\nBest regards,\nRitika Chouhan"),
        }

    def send(self, draft: Draft) -> None:
        raise ToolUnavailable("Gmail can't send: reconnect the Gmail connector")

    def job_emails(self) -> list[dict]:
        if self.inbox_fixture and Path(self.inbox_fixture).exists():
            return json.loads(Path(self.inbox_fixture).read_text(encoding="utf-8"))
        return []


@dataclass
class OfflineCalendar:
    booked: list[Interview] = field(default_factory=list)

    def propose_slots(self, interview: Interview) -> list[str]:
        return ["Tue 10:00 IST", "Wed 15:30 IST", "Thu 19:00 IST"]

    def book(self, interview: Interview) -> None:
        self.booked.append(interview)


@dataclass
class Adapters:
    source: JobSource
    cv_maker: CVMaker
    applier: Applier
    mailer: Mailer
    calendar: Calendar
    master_cv: str
    company_tiers: dict[str, float] = field(default_factory=dict)  # 0-1, for interview priority
