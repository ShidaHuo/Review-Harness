#!/usr/bin/env python3
"""Locate Review Harness from its managed pointer or bounded local candidates."""

from __future__ import annotations

import json
import os
import sys
from importlib.util import find_spec
from pathlib import Path

REQUIRED_PATHS = (
    Path("AGENTS.md"),
    Path("runtime_adapter.py"),
    Path("src/review_harness"),
    Path(".dsh/skills/research-topic-evaluation/SKILL.md"),
    Path(".dsh/skills/review-landscape-analysis/SKILL.md"),
    Path(".dsh/skills/review-outline-design/SKILL.md"),
    Path(".dsh/skills/review-outline-export/SKILL.md"),
)


def is_project_root(path: Path) -> bool:
    return path.is_dir() and all((path / relative).exists() for relative in REQUIRED_PATHS)


def bounded_ancestors(path: Path, limit: int = 5) -> list[Path]:
    current = path.resolve()
    candidates: list[Path] = []
    for _ in range(limit):
        candidates.append(current)
        if current.parent == current:
            break
        current = current.parent
    return candidates


def managed_project_root() -> Path | None:
    """Read the non-secret project path written beside the installed Skill."""
    pointer = Path(__file__).resolve().parents[1] / "project-root.txt"
    if not pointer.is_file():
        return None
    lines = [line.strip() for line in pointer.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    if len(lines) != 1:
        return None
    return Path(lines[0]).expanduser()


def candidate_roots() -> list[Path]:
    candidates: list[Path] = []

    configured = os.getenv("REVIEW_HARNESS_HOME")
    if configured and configured.strip():
        candidates.append(Path(configured).expanduser())

    managed = managed_project_root()
    if managed is not None:
        candidates.append(managed)

    spec = find_spec("review_harness")
    if spec and spec.origin:
        candidates.extend(bounded_ancestors(Path(spec.origin).parent))

    candidates.extend(bounded_ancestors(Path.cwd()))
    candidates.extend(bounded_ancestors(Path(__file__).parent))

    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        key = os.path.normcase(str(resolved))
        if key not in seen:
            seen.add(key)
            unique.append(resolved)
    return unique


def key_is_configured(project_root: Path) -> bool:
    if os.getenv("OPENALEX_API_KEY", "").strip():
        return True
    configured_file = os.getenv("OPENALEX_API_KEY_FILE", "").strip()
    if configured_file:
        return Path(configured_file).expanduser().is_file()
    return (project_root / "OPENALEX_API_KEY.txt").is_file()


def main() -> int:
    for candidate in candidate_roots():
        if is_project_root(candidate):
            result = {
                "status": "ready",
                "project_root": str(candidate),
                "workflow_contract": str(candidate / "AGENTS.md"),
                "runtime_adapter": str(candidate / "runtime_adapter.py"),
                "openalex_key_configured": key_is_configured(candidate),
            }
            print(json.dumps(result, ensure_ascii=False))
            return 0

    print(
        json.dumps(
            {
                "status": "not_found",
                "error": (
                    "Review Harness was not found. Re-run setup-codex from the Review Harness "
                    "repository or set REVIEW_HARNESS_HOME to its project root."
                ),
            },
            ensure_ascii=False,
        ),
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
