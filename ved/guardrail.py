"""Guardrail and hallucination checks (the ved-guardrail-agent rules, in code).

Every line of a CV or email must be supported by the source facts (the Master CV and the JD).
The check is deliberately strict: anything it can't trace back is flagged, not guessed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# Phrases that overstated Ritika's record in earlier CV drafts.
OVERSTATEMENT_PATTERNS = [
    r"\bdeep (knowledge|expertise)\b", r"\bexecutive[- ]level\b", r"\bin production\b",
    r"\bdrove adoption\b", r"\bdrives adoption\b", r"\bworld[- ]class\b", r"\bexpert in\b",
    r"\bdaily\b", r"\bdecide[sd]? what ships\b", r"\bowned (the )?budget\b",
]
# Never disclose pay in outreach unless Ritika approved it.
CTC_PATTERN = r"\b(ctc|lpa|salary|current (pay|compensation))\b|₹\s?\d"
NUMBER_PATTERN = r"\d+(?:\.\d+)?\s?(?:%|x|\+|k|m|lpa|years?|yrs?)?"


@dataclass
class Finding:
    line: str
    reason: str


@dataclass
class Result:
    text: str
    lines_checked: int = 0
    findings: list[Finding] = field(default_factory=list)
    fixed: int = 0

    @property
    def verdict(self) -> str:
        if not self.findings:
            return "pass"
        return "fixed" if self.fixed == len(self.findings) else "blocked"


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower()).strip()


def _numbers(s: str) -> set[str]:
    return {_norm(n) for n in re.findall(NUMBER_PATTERN, s.lower()) if re.search(r"\d", n)}


def check_text(text: str, source_facts: str, *, allow_ctc: bool = False, auto_fix: bool = True) -> Result:
    """Check each non-empty line against the source facts.

    - Any number (%, years, counts) must appear in the source.
    - Overstatement phrases are flagged; with auto_fix the line is dropped rather than reworded,
      because rewording is a judgement call the CV maker (or Ritika) should make.
    - Pay/CTC mentions are blocked unless allow_ctc.
    """
    src_bare = set(re.findall(r"\d+(?:\.\d+)?", source_facts))
    res = Result(text=text)
    kept: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            kept.append(raw)
            continue
        res.lines_checked += 1
        reasons = []
        for n in sorted(_numbers(line)):
            if re.match(r"\d+(?:\.\d+)?", n).group(0) not in src_bare:
                reasons.append(f"number '{n}' not in source")
        for pat in OVERSTATEMENT_PATTERNS:
            if re.search(pat, line, re.I) and not re.search(pat, source_facts, re.I):
                reasons.append(f"overstatement '{re.search(pat, line, re.I).group(0)}'")
        if not allow_ctc and re.search(CTC_PATTERN, line, re.I):
            reasons.append("pay/CTC disclosed without approval")
        if reasons:
            res.findings.append(Finding(line, "; ".join(reasons)))
            if auto_fix and not any(r.startswith("pay/CTC") for r in reasons):
                res.fixed += 1
                continue  # drop the unsupported line
        kept.append(raw)
    res.text = "\n".join(kept)
    return res
