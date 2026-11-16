"""Shared state for the VED LangGraph pipeline."""
from __future__ import annotations

import operator
from typing import Annotated, Literal, TypedDict

RunMode = Literal["live", "scheduled", "status"]

# The tracker status state machine. A stage may only move a row along one of these edges.
STATUSES = [
    "New", "Shortlisted", "Maybe", "Skipped", "CV ready", "Approved to apply",
    "Applied", "Outreach sent", "Interview", "Offer", "Rejected", "Withdrawn",
]
TRANSITIONS: dict[str, set[str]] = {
    "New": {"Shortlisted", "Maybe", "Skipped"},
    "Maybe": {"Shortlisted", "Skipped", "Withdrawn"},
    "Shortlisted": {"CV ready", "Skipped", "Withdrawn"},
    "CV ready": {"Approved to apply", "Shortlisted", "Withdrawn"},
    "Approved to apply": {"Applied", "Shortlisted", "Withdrawn"},
    "Applied": {"Outreach sent", "Interview", "Rejected", "Withdrawn"},
    "Outreach sent": {"Interview", "Rejected", "Withdrawn"},
    "Interview": {"Offer", "Rejected", "Withdrawn"},
    "Skipped": set(), "Offer": set(), "Rejected": set(), "Withdrawn": set(),
}

# Per-run limits (from the orchestrator skill).
MAX_CVS_PER_RUN = 5
MAX_APPS_PER_COMPANY = 3
MAX_OUTREACH_PER_COMPANY = 2


class Job(TypedDict, total=False):
    id: str
    score: int
    status: str
    company: str
    title: str
    location: str
    sponsorship: str
    pay_range: str
    job_url: str
    date_found: str
    cv_url: str
    coverage: int
    applied_on: str
    follow_up_due: str
    notes: str
    jd_text: str  # not written to the tracker


class Draft(TypedDict, total=False):
    job_id: str
    kind: Literal["cv", "email", "reply"]
    to: str
    subject: str
    body: str
    guardrail: str  # "pass" | "fixed" | "blocked"


class Interview(TypedDict, total=False):
    job_id: str
    company: str
    role: str
    round: str
    priority: str  # P1 / P2 / P3
    score: int
    calendar_tag: str
    proposed_slots: list[str]
    chosen_slot: str
    booked: bool
    fit: dict[str, float]  # scoring parts, consumed by the schedule node


class GuardrailEntry(TypedDict):
    area: str
    items_checked: int
    issues_found: int
    issues_fixed: int
    needs_ritika: list[str]


class VEDState(TypedDict, total=False):
    mode: RunMode
    run_date: str
    jobs: list[Job]                      # whole tracker, replaced by each node that changes it
    drafts: list[Draft]                  # CVs/emails waiting on a gate
    interviews: list[Interview]
    blocked: Annotated[list[str], operator.add]      # pre-flight / stage failures
    guardrail_log: Annotated[list[GuardrailEntry], operator.add]
    events: Annotated[list[str], operator.add]       # audit trail of every status change
    report: str
