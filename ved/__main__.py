"""VED command line.

  python -m ved run    --mode live|scheduled|status --thread 2026-11-16
  python -m ved resume --thread 2026-11-16 --decision '{"approve": ["<job id>"]}'

State is checkpointed in SQLite (--db), so a run paused at a gate can be resumed later,
from another process. The tracker CSV is written after every run or resume.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from . import tracker
from .adapters import (Adapters, FixtureSource, OfflineCalendar, OfflineMailer, ReuseFirstCVMaker,
                       UnavailableApplier)
from .graph import build_graph


def _adapters(a) -> Adapters:
    return Adapters(
        source=FixtureSource(Path(a.jobs)),
        cv_maker=ReuseFirstCVMaker(Path(a.cv_dir)),
        applier=UnavailableApplier(),
        mailer=OfflineMailer(Path(a.inbox) if a.inbox else None),
        calendar=OfflineCalendar(),
        master_cv=Path(a.master_cv).read_text(encoding="utf-8") if Path(a.master_cv).exists() else "",
    )


def _print(result: dict) -> None:
    if result.get("__interrupt__"):
        for it in result["__interrupt__"]:
            print("⏸  Paused at gate", it.value["gate"], "–", it.value["question"])
            print(json.dumps(it.value["items"], indent=2, ensure_ascii=False))
        print("\nResume with: python -m ved resume --thread <id> --decision '<json>'")
    else:
        print(result.get("report", ""))


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="ved")
    p.add_argument("command", choices=["run", "resume"])
    p.add_argument("--mode", default="live", choices=["live", "scheduled", "status"])
    p.add_argument("--thread", required=True, help="run id, e.g. today's date")
    p.add_argument("--decision", default="{}", help="JSON answer for the gate the run is paused at")
    p.add_argument("--tracker", default="data/job_tracker.csv")
    p.add_argument("--jobs", default="examples/jobs.json")
    p.add_argument("--inbox", default="")
    p.add_argument("--master-cv", default="data/master_cv.md")
    p.add_argument("--cv-dir", default="cvs")
    p.add_argument("--db", default="data/ved_checkpoints.sqlite")
    a = p.parse_args(argv)

    Path(a.db).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(a.db, check_same_thread=False) as conn:
        app = build_graph(_adapters(a), SqliteSaver(conn))
        cfg = {"configurable": {"thread_id": a.thread}}
        if a.command == "run":
            result = app.invoke({"mode": a.mode, "jobs": tracker.load(a.tracker)}, cfg)
        else:
            result = app.invoke(Command(resume=json.loads(a.decision)), cfg)
        tracker.save(a.tracker, app.get_state(cfg).values.get("jobs", []))
        _print(result)


if __name__ == "__main__":
    main()
