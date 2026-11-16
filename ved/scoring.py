"""Job-fit scoring and interview priority, matching the Scoring Rules tab."""
from __future__ import annotations

JOB_WEIGHTS = {"role_fit": 30, "skills": 30, "domain": 15, "seniority": 15, "feasibility": 10}
PRIORITY_WEIGHTS = {"skills": 35, "company_tier": 25, "pay": 20, "feasibility": 10, "stage": 10}
CALENDAR = {"P1": ("[P1 🟢]", "10"), "P2": ("[P2 🟡]", "5"), "P3": ("[P3 🔴]", "11")}


def _weighted(parts: dict[str, float], weights: dict[str, int]) -> int:
    """Each part is a 0-1 fraction; missing parts count as 0."""
    for k, v in parts.items():
        if k not in weights:
            raise KeyError(f"unknown scoring part: {k}")
        if not 0 <= v <= 1:
            raise ValueError(f"{k} must be between 0 and 1, got {v}")
    return round(sum(weights[k] * parts.get(k, 0) for k in weights))


def job_score(parts: dict[str, float]) -> int:
    return _weighted(parts, JOB_WEIGHTS)


def job_status(score: int) -> str:
    if score >= 70:
        return "Shortlisted"
    if score >= 55:
        return "Maybe"
    return "Skipped"


def interview_priority(parts: dict[str, float]) -> tuple[int, str, str, str]:
    """Returns (score, priority, title tag, Google Calendar colorId)."""
    score = _weighted(parts, PRIORITY_WEIGHTS)
    p = "P1" if score >= 75 else "P2" if score >= 55 else "P3"
    tag, color = CALENDAR[p]
    return score, p, tag, color
