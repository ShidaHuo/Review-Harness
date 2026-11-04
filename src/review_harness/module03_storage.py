from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import new_id, utc_now
from .module02_storage import get_module02_run, init_module02_schema
from .storage import connect

MODULE03_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS module03_outline_runs (
    id TEXT PRIMARY KEY,
    module02_run_id TEXT NOT NULL REFERENCES module02_runs(id),
    perspective_branch_id TEXT NOT NULL UNIQUE REFERENCES module03_perspective_branches(id),
    perspective_rank INTEGER NOT NULL,
    status TEXT NOT NULL,
    current_version INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    approved_at TEXT
);

CREATE TABLE IF NOT EXISTS module03_outline_versions (
    id TEXT PRIMARY KEY,
    module03_run_id TEXT NOT NULL REFERENCES module03_outline_runs(id),
    version INTEGER NOT NULL,
    outline_json TEXT NOT NULL,
    actor TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(module03_run_id, version)
);

CREATE TABLE IF NOT EXISTS module03_outline_feedback (
    id TEXT PRIMARY KEY,
    module03_run_id TEXT NOT NULL REFERENCES module03_outline_runs(id),
    target_version INTEGER NOT NULL,
    decision TEXT NOT NULL,
    feedback TEXT,
    created_at TEXT NOT NULL
);
"""


def init_module03_schema(db_path: Path) -> None:
    init_module02_schema(db_path)
    with connect(db_path) as connection:
        connection.executescript(MODULE03_SCHEMA_SQL)


def start_module03_outline(db_path: Path, module02_run_id: str, perspective_rank: int) -> str:
    init_module03_schema(db_path)
    module02 = get_module02_run(db_path, module02_run_id)
    if module02["status"] != "perspectives_ready":
        raise ValueError("Module 03 requires a perspectives_ready Module 02 run")
    with connect(db_path) as connection:
        branch = connection.execute(
            """
            SELECT id, status FROM module03_perspective_branches
            WHERE module02_run_id = ? AND perspective_rank = ?
            """,
            (module02_run_id, perspective_rank),
        ).fetchone()
        if branch is None:
            raise KeyError(f"Unknown perspective rank for Module 02: {perspective_rank}")
        if branch["status"] != "selected_for_module03":
            raise PermissionError("Select the perspective before starting Module 03")
        existing = connection.execute(
            "SELECT id FROM module03_outline_runs WHERE perspective_branch_id = ?",
            (branch["id"],),
        ).fetchone()
        if existing:
            return str(existing["id"])
        run_id = new_id("module03")
        now = utc_now()
        connection.execute(
            """
            INSERT INTO module03_outline_runs(
                id, module02_run_id, perspective_branch_id, perspective_rank,
                status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, 'drafting_outline', ?, ?)
            """,
            (run_id, module02_run_id, branch["id"], perspective_rank, now, now),
        )
    return run_id


def get_module03_run(db_path: Path, module03_run_id: str) -> dict[str, Any]:
    init_module03_schema(db_path)
    with connect(db_path) as connection:
        row = connection.execute(
            """
            SELECT r.*, b.perspective_title, b.perspective_json, b.dsh_session_id
            FROM module03_outline_runs r
            JOIN module03_perspective_branches b ON b.id = r.perspective_branch_id
            WHERE r.id = ?
            """,
            (module03_run_id,),
        ).fetchone()
    if row is None:
        raise KeyError(f"Unknown Module 03 run: {module03_run_id}")
    result = dict(row)
    result["perspective"] = json.loads(result.pop("perspective_json"))
    return result


def latest_outline(db_path: Path, module03_run_id: str) -> dict[str, Any] | None:
    get_module03_run(db_path, module03_run_id)
    with connect(db_path) as connection:
        row = connection.execute(
            """
            SELECT version, outline_json, actor, created_at
            FROM module03_outline_versions
            WHERE module03_run_id = ? ORDER BY version DESC LIMIT 1
            """,
            (module03_run_id,),
        ).fetchone()
    if row is None:
        return None
    result = dict(row)
    result["outline"] = json.loads(result.pop("outline_json"))
    return result


def _number_key(value: str) -> tuple[int, ...]:
    try:
        parts = tuple(int(item) for item in value.split("."))
    except ValueError as exc:
        raise ValueError(f"Invalid outline section number: {value}") from exc
    if not 1 <= len(parts) <= 4 or any(item < 1 for item in parts):
        raise ValueError(f"Invalid outline section number: {value}")
    return parts


def _validate_outline(outline: dict[str, Any], module03_run_id: str) -> None:
    if outline.get("module03_run_id") != module03_run_id:
        raise ValueError("Outline module03_run_id does not match the target run")
    for field in (
        "candidate_title",
        "title_rationale",
        "organizing_principle",
        "intended_audience",
        "scope_statement",
    ):
        if not str(outline.get(field) or "").strip():
            raise ValueError(f"Outline field is required: {field}")
    sections = outline.get("sections")
    if not isinstance(sections, list) or not 4 <= len(sections) <= 60:
        raise ValueError("Outline requires between 4 and 60 section records")
    numbers = [str(section.get("number") or "") for section in sections]
    if len(numbers) != len(set(numbers)):
        raise ValueError("Outline section numbers must be unique")
    keys = [_number_key(number) for number in numbers]
    if keys != sorted(keys):
        raise ValueError("Outline sections must be stored in numeric reading order")
    available_numbers = set(numbers)
    top_level = [key[0] for key in keys if len(key) == 1]
    if top_level != list(range(1, len(top_level) + 1)) or not 3 <= len(top_level) <= 10:
        raise ValueError("Top-level sections must be consecutive and number between 3 and 10")
    sibling_groups: dict[tuple[int, ...], list[int]] = {}
    for section, key in zip(sections, keys, strict=True):
        if section.get("level") != len(key):
            raise ValueError(f"Section {section.get('number')} level does not match its number")
        if len(key) > 1:
            parent = ".".join(str(item) for item in key[:-1])
            if parent not in available_numbers:
                raise ValueError(f"Section {section['number']} has no parent section {parent}")
            sibling_groups.setdefault(key[:-1], []).append(key[-1])
        for field in ("title", "purpose", "rationale", "expected_takeaway"):
            if not str(section.get(field) or "").strip():
                raise ValueError(f"Section {section['number']} is missing {field}")
        for field in ("writing_logic", "key_questions"):
            values = section.get(field)
            if not isinstance(values, list) or not values or any(not str(item).strip() for item in values):
                raise ValueError(f"Section {section['number']} requires non-empty {field}")
        evidence_ids = section.get("evidence_ids")
        if not isinstance(evidence_ids, list) or len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError(f"Section {section['number']} evidence_ids must be a unique list")
    for parent, siblings in sibling_groups.items():
        if siblings != list(range(1, len(siblings) + 1)):
            raise ValueError(f"Child sections under {parent} must be consecutive")
    titles = " ".join(str(section["title"]).casefold() for section in sections if section["level"] == 1)
    if not any(token in titles for token in ("introduction", "引言", "绪论")):
        raise ValueError("Outline requires an introduction top-level section")
    if not any(token in titles for token in ("future", "outlook", "perspective", "展望", "未来")):
        raise ValueError("Outline requires a future-perspective top-level section")


def _available_evidence_ids(db_path: Path, module02_run_id: str) -> set[str]:
    with connect(db_path) as connection:
        review_ids = {
            str(row[0]) for row in connection.execute(
                "SELECT id FROM module02_reviews WHERE module02_run_id = ? AND relevance_status = 'included'",
                (module02_run_id,),
            )
        }
        paper_ids = {
            str(row[0]) for row in connection.execute(
                "SELECT paper_id FROM module02_research WHERE module02_run_id = ? AND category != 'excluded'",
                (module02_run_id,),
            )
        }
        trend_ids = {
            str(row[0]) for row in connection.execute(
                "SELECT id FROM module02_trend_claims WHERE module02_run_id = ?",
                (module02_run_id,),
            )
        }
    return review_ids | paper_ids | trend_ids


def save_outline_version(
    db_path: Path,
    module03_run_id: str,
    outline: dict[str, Any],
    *,
    actor: str,
) -> int:
    run = get_module03_run(db_path, module03_run_id)
    if run["status"] not in {"drafting_outline", "revision_requested"}:
        raise ValueError("Outline can be saved only for a new draft or requested revision")
    _validate_outline(outline, module03_run_id)
    available_ids = _available_evidence_ids(db_path, run["module02_run_id"])
    claimed_ids = {
        evidence_id
        for section in outline["sections"]
        for evidence_id in section.get("evidence_ids", [])
    }
    unknown_ids = claimed_ids - available_ids
    if unknown_ids:
        raise KeyError(f"Outline cites unknown Module 02 evidence ids: {sorted(unknown_ids)}")
    next_version = int(run["current_version"]) + 1
    now = utc_now()
    with connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO module03_outline_versions(
                id, module03_run_id, version, outline_json, actor, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                new_id("outline"),
                module03_run_id,
                next_version,
                json.dumps(outline, ensure_ascii=False),
                actor,
                now,
            ),
        )
        connection.execute(
            """
            UPDATE module03_outline_runs
            SET current_version = ?, status = 'awaiting_outline_feedback', updated_at = ?
            WHERE id = ?
            """,
            (next_version, now, module03_run_id),
        )
    return next_version


def record_outline_feedback(
    db_path: Path,
    module03_run_id: str,
    decision: str,
    feedback: str | None = None,
) -> dict[str, Any]:
    run = get_module03_run(db_path, module03_run_id)
    if run["status"] != "awaiting_outline_feedback":
        raise ValueError("Outline feedback requires a displayed outline awaiting feedback")
    if decision not in {"approved", "revise"}:
        raise ValueError("Outline decision must be approved or revise")
    normalized_feedback = (feedback or "").strip() or None
    if decision == "revise" and normalized_feedback is None:
        raise ValueError("A revision decision requires concrete user feedback")
    now = utc_now()
    status = "outline_approved" if decision == "approved" else "revision_requested"
    with connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO module03_outline_feedback(
                id, module03_run_id, target_version, decision, feedback, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                new_id("outlinefeedback"),
                module03_run_id,
                run["current_version"],
                decision,
                normalized_feedback,
                now,
            ),
        )
        connection.execute(
            """
            UPDATE module03_outline_runs
            SET status = ?, updated_at = ?, approved_at = ?
            WHERE id = ?
            """,
            (status, now, now if decision == "approved" else None, module03_run_id),
        )
    return {
        "module03_run_id": module03_run_id,
        "version": run["current_version"],
        "status": status,
        "feedback": normalized_feedback,
    }


def module03_next_action(db_path: Path, module03_run_id: str) -> dict[str, Any]:
    run = get_module03_run(db_path, module03_run_id)
    if run["status"] == "drafting_outline":
        action = "create_outline"
        blocking = False
    elif run["status"] == "revision_requested":
        action = "revise_outline"
        blocking = False
    elif run["status"] == "awaiting_outline_feedback":
        action = "collect_outline_feedback"
        blocking = True
    elif run["status"] == "outline_approved":
        with connect(db_path) as connection:
            has_manuscript_table = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'module04_manuscript_runs'"
            ).fetchone() is not None
            manuscript = None
            module05 = None
            if has_manuscript_table:
                manuscript = connection.execute(
                    "SELECT id, status FROM module04_manuscript_runs WHERE module03_run_id = ?",
                    (module03_run_id,),
                ).fetchone()
            has_module05_table = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'module05_runs'"
            ).fetchone() is not None
            if manuscript is not None and has_module05_table:
                module05 = connection.execute(
                    "SELECT id, status FROM module05_runs WHERE module04_run_id = ?",
                    (manuscript["id"],),
                ).fetchone()
        if manuscript is None:
            action = "run_module04"
        elif manuscript["status"] != "completed":
            action = "continue_module04"
        elif module05 is None:
            action = "start_module05"
        elif module05["status"] == "completed":
            action = "mvp_complete"
        else:
            action = "continue_module05"
        blocking = False
    else:
        raise ValueError(f"Unknown Module 03 outline status: {run['status']}")
    result = {
        "module03_run_id": module03_run_id,
        "module02_run_id": run["module02_run_id"],
        "perspective_rank": run["perspective_rank"],
        "perspective_title": run["perspective_title"],
        "current_version": run["current_version"],
        "status": run["status"],
        "action": action,
        "blocking_user_input": blocking,
        "terminal": action == "mvp_complete",
    }
    if action in {"continue_module04", "start_module05"}:
        result["module04_run_id"] = manuscript["id"]
    if action == "continue_module05":
        result["module04_run_id"] = manuscript["id"]
        result["module05_run_id"] = module05["id"]
    if action == "revise_outline":
        with connect(db_path) as connection:
            row = connection.execute(
                """
                SELECT feedback FROM module03_outline_feedback
                WHERE module03_run_id = ? AND decision = 'revise'
                ORDER BY created_at DESC, rowid DESC LIMIT 1
                """,
                (module03_run_id,),
            ).fetchone()
        result["latest_feedback"] = row["feedback"] if row else None
    return result
