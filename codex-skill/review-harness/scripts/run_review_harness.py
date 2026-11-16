#!/usr/bin/env python3
"""Load Review Harness from its installation while keeping the caller's workspace."""

from __future__ import annotations

import sys
import os
import json
import io
import contextlib
from pathlib import Path

from locate_review_harness import candidate_roots, is_project_root


def resolve_project_root() -> Path:
    for candidate in candidate_roots():
        if is_project_root(candidate):
            return candidate
    raise RuntimeError(
        "Review Harness project root is unavailable. Re-run setup-codex or set REVIEW_HARNESS_HOME."
    )


def main() -> int:
    project_root = resolve_project_root()
    source_root = str(project_root / "src")
    if source_root not in sys.path:
        sys.path.insert(0, source_root)

    from review_harness.cli import main as cli_main

    args = sys.argv[1:]
    if "create-run" not in args:
        return cli_main(args)
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        result = cli_main(args)
    value = output.getvalue()
    print(value, end="")
    session = os.environ.get("CODEX_SESSION_ID")
    if result == 0 and session and all(c.isalnum() or c in "-_" for c in session):
        payload = json.loads(value)
        db = Path(args[args.index("--db") + 1]) if "--db" in args else Path("runtime/research.sqlite3")
        marker = Path("runtime") / "review-harness-sessions" / (session + ".json")
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(json.dumps({"run_id": payload["run_id"], "db": str(db.resolve())}), encoding="utf-8")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
