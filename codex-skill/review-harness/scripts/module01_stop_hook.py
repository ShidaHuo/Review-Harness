#!/usr/bin/env python3
"""Continue unfinished review work at supported gates, scoped to its session."""
import hashlib
import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

from locate_review_harness import candidate_roots, is_project_root


def check(event):
    session = event.get("session_id", "")
    if not session or not all(c.isalnum() or c in "-_" for c in session):
        return {}
    cwd = Path(event.get("cwd", ""))
    marker = cwd / "runtime" / "review-harness-sessions" / (session + ".json")
    if not marker.is_file():
        return {}
    data = json.loads(marker.read_text(encoding="utf-8"))
    db = Path(data["db"])
    if not db.is_file():
        return {}
    root = next(p for p in candidate_roots() if is_project_root(p))
    sys.path.insert(0, str(root / "src"))
    from review_harness.storage import module01_next_action, status_for_run
    status = status_for_run(db, data["run_id"])
    if any(s["status"] == "failed" for s in status["searches"]):
        return {}
    if status.get("latest_decision"):
        with closing(sqlite3.connect(f"{db.resolve().as_uri()}?mode=ro", uri=True)) as connection:
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {"module02_runs", "module03_outline_runs"} <= tables:
                return {}
            outline = connection.execute("""SELECT m3.id FROM module03_outline_runs m3
                JOIN module02_runs m2 ON m2.id=m3.module02_run_id
                WHERE m2.topic_run_id=? ORDER BY m3.updated_at DESC LIMIT 1""", (data["run_id"],)).fetchone()
            if not outline:
                return {}
            row = connection.execute("""SELECT m4.id, m4.status FROM module04_manuscript_runs m4
                JOIN module03_outline_runs m3 ON m3.id=m4.module03_run_id
                JOIN module02_runs m2 ON m2.id=m3.module02_run_id
                WHERE m3.id=? ORDER BY m4.updated_at DESC LIMIT 1""", (outline[0],)).fetchone() if "module04_manuscript_runs" in tables else None
        if row:
            if row[1] not in {"drafting_manuscript", "manuscript_revision", "export_ready"}:
                return {}
            action = {"module04_run_id": row[0], "action": "export_markdown" if row[1] == "export_ready" else "write_complete_manuscript"}
        else:
            from review_harness.module03_storage import module03_next_action
            action = module03_next_action(db, outline[0])
            if action.get("terminal") or action.get("blocking_user_input"):
                return {}
    else:
        action = module01_next_action(db, data["run_id"])
        if action["action"] not in {"search_literature", "screen_papers", "synthesize_report_and_decide"}:
            return {}
    fingerprint = hashlib.sha256(json.dumps(action, sort_keys=True).encode()).hexdigest()
    if data.get("last_fingerprint") == fingerprint:
        return {}
    data["last_fingerprint"] = fingerprint
    marker.write_text(json.dumps(data), encoding="utf-8")
    return {"decision": "block", "reason": "The review workflow remains unfinished. Continue the existing run in the same workspace: " + json.dumps(action, ensure_ascii=False)}


if __name__ == "__main__":
    try:
        print(json.dumps(check(json.load(sys.stdin)), ensure_ascii=False))
    except (OSError, ValueError, KeyError, StopIteration, sqlite3.Error):
        print("{}")
