from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .models import new_id, utc_now
from .module03_storage import get_module03_run, latest_outline, init_module03_schema
from .storage import connect

TARGET_CHARACTERS = 15_000
MIN_CHARACTERS = 13_500
MAX_CHARACTERS = 16_500

MODULE04_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS module04_manuscript_runs (
    id TEXT PRIMARY KEY,
    module03_run_id TEXT NOT NULL UNIQUE REFERENCES module03_outline_runs(id),
    outline_version INTEGER NOT NULL,
    status TEXT NOT NULL,
    target_characters INTEGER NOT NULL,
    min_characters INTEGER NOT NULL,
    max_characters INTEGER NOT NULL,
    manuscript_markdown TEXT,
    manuscript_character_count INTEGER,
    evidence_ids_json TEXT NOT NULL DEFAULT '[]',
    figure_count INTEGER NOT NULL DEFAULT 0,
    table_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS module04_exports (
    id TEXT PRIMARY KEY,
    module03_run_id TEXT NOT NULL UNIQUE REFERENCES module03_outline_runs(id),
    outline_version INTEGER NOT NULL,
    output_path TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    status TEXT NOT NULL,
    exported_at TEXT NOT NULL
);
"""


def init_module04_schema(db_path: Path) -> None:
    init_module03_schema(db_path)
    with connect(db_path) as connection:
        connection.executescript(MODULE04_SCHEMA_SQL)
        columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(module04_manuscript_runs)")
        }
        migrations = {
            "manuscript_markdown": "TEXT",
            "manuscript_character_count": "INTEGER",
            "evidence_ids_json": "TEXT NOT NULL DEFAULT '[]'",
            "figure_count": "INTEGER NOT NULL DEFAULT 0",
            "table_count": "INTEGER NOT NULL DEFAULT 0",
        }
        for column, declaration in migrations.items():
            if column not in columns:
                connection.execute(
                    f"ALTER TABLE module04_manuscript_runs ADD COLUMN {column} {declaration}"
                )
        legacy_rows = connection.execute(
            """
            SELECT module03_run_id FROM module04_manuscript_runs
            WHERE manuscript_markdown IS NULL
            """
        ).fetchall()
        if legacy_rows:
            connection.execute(
                """
                UPDATE module04_manuscript_runs
                SET status = 'drafting_manuscript', completed_at = NULL
                WHERE manuscript_markdown IS NULL
                """
            )
            connection.executemany(
                "DELETE FROM module04_exports WHERE module03_run_id = ?",
                [(row["module03_run_id"],) for row in legacy_rows],
            )


def start_module04_manuscript(
    db_path: Path,
    module03_run_id: str,
    target_characters: int = TARGET_CHARACTERS,
) -> str:
    init_module04_schema(db_path)
    run = get_module03_run(db_path, module03_run_id)
    if run["status"] != "outline_approved":
        raise PermissionError("Module 04 requires an explicitly approved Module 03 outline")
    latest = latest_outline(db_path, module03_run_id)
    if latest is None:
        raise ValueError("Module 04 requires a persisted approved outline")
    if not 10_000 <= target_characters <= 25_000:
        raise ValueError("Module 04 target must be between 10,000 and 25,000 characters")
    minimum = round(target_characters * 0.9)
    maximum = round(target_characters * 1.1)
    with connect(db_path) as connection:
        existing = connection.execute(
            "SELECT id FROM module04_manuscript_runs WHERE module03_run_id = ?",
            (module03_run_id,),
        ).fetchone()
        if existing:
            return str(existing["id"])
        run_id = new_id("module04")
        now = utc_now()
        connection.execute(
            """
            INSERT INTO module04_manuscript_runs(
                id, module03_run_id, outline_version, status,
                target_characters, min_characters, max_characters,
                created_at, updated_at
            ) VALUES (?, ?, ?, 'drafting_manuscript', ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                module03_run_id,
                latest["version"],
                target_characters,
                minimum,
                maximum,
                now,
                now,
            ),
        )
    return run_id


def get_module04_run(db_path: Path, module04_run_id: str) -> dict[str, Any]:
    init_module04_schema(db_path)
    with connect(db_path) as connection:
        row = connection.execute(
            "SELECT * FROM module04_manuscript_runs WHERE id = ?",
            (module04_run_id,),
        ).fetchone()
    if row is None:
        raise KeyError(f"Unknown Module 04 run: {module04_run_id}")
    result = dict(row)
    result["evidence_ids"] = json.loads(result.pop("evidence_ids_json") or "[]")
    return result


def _available_evidence_ids(db_path: Path, module04_run_id: str) -> set[str]:
    run = get_module04_run(db_path, module04_run_id)
    module03 = get_module03_run(db_path, run["module03_run_id"])
    with connect(db_path) as connection:
        review_ids = {
            str(row[0]) for row in connection.execute(
                "SELECT id FROM module02_reviews WHERE module02_run_id = ? AND relevance_status = 'included'",
                (module03["module02_run_id"],),
            )
        }
        paper_ids = {
            str(row[0]) for row in connection.execute(
                "SELECT paper_id FROM module02_research WHERE module02_run_id = ? AND category != 'excluded'",
                (module03["module02_run_id"],),
            )
        }
        trend_ids = {
            str(row[0]) for row in connection.execute(
                "SELECT id FROM module02_trend_claims WHERE module02_run_id = ?",
                (module03["module02_run_id"],),
            )
        }
    return review_ids | paper_ids | trend_ids


def _body_character_count(markdown: str) -> int:
    body = re.split(r"^##\s+参考文献", markdown, maxsplit=1, flags=re.MULTILINE)[0]
    body = "\n".join(
        line for line in body.splitlines()
        if not re.match(r"^>\s*\*{0,2}\[?(?:图|表)\s*\d+", line.strip())
    )
    body = re.sub(r"[`#>*_~|\-]", "", body)
    body = re.sub(r"\s+", "", body)
    return len(body)


def _required_outline_numbers(db_path: Path, module03_run_id: str) -> set[str]:
    outline = latest_outline(db_path, module03_run_id)
    if outline is None:
        raise ValueError("Frozen outline is missing")
    return {str(item["number"]) for item in outline["outline"]["sections"]}


def save_complete_manuscript(
    db_path: Path,
    module04_run_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    run = get_module04_run(db_path, module04_run_id)
    if run["status"] not in {"drafting_manuscript", "manuscript_revision"}:
        raise ValueError("Complete manuscript can be saved only during drafting or revision")
    if payload.get("module04_run_id") != module04_run_id:
        raise ValueError("Manuscript module04_run_id does not match")
    markdown = str(payload.get("markdown") or "").strip()
    if not markdown:
        raise ValueError("Complete manuscript Markdown is required")
    if not re.search(r"^##\s+摘要", markdown, flags=re.MULTILINE):
        raise ValueError("Complete manuscript requires a Markdown abstract heading")
    if not re.search(r"^##\s+参考文献", markdown, flags=re.MULTILINE):
        raise ValueError("Complete manuscript requires a reference heading")
    heading_numbers = {
        match.group(1)
        for match in re.finditer(r"^#{2,6}\s+(\d+(?:\.\d+)*)\s+", markdown, flags=re.MULTILINE)
    }
    required_numbers = _required_outline_numbers(db_path, run["module03_run_id"])
    missing_headings = sorted(required_numbers - heading_numbers)
    if missing_headings:
        raise ValueError(f"Manuscript is missing frozen outline headings: {missing_headings}")
    evidence_ids = list(payload.get("evidence_ids", []))
    if len(evidence_ids) != len(set(evidence_ids)):
        raise ValueError("Manuscript evidence ids must be unique")
    available = _available_evidence_ids(db_path, module04_run_id)
    unknown = set(evidence_ids) - available
    if unknown:
        raise KeyError(f"Manuscript lists unknown Module 02 evidence ids: {sorted(unknown)}")
    exposed = [evidence_id for evidence_id in evidence_ids if evidence_id in markdown]
    if exposed:
        raise ValueError("User-facing manuscript must not expose internal evidence ids")
    character_count = _body_character_count(markdown)
    if not run["min_characters"] <= character_count <= run["max_characters"]:
        raise ValueError(
            f"Manuscript body has {character_count} characters; required range is "
            f"{run['min_characters']}-{run['max_characters']}"
        )
    figure_count = len(re.findall(r"(?:\[图\s*\d+\s*置于此处|【图\s*\d+.*?位置】)", markdown))
    table_count = len(re.findall(r"(?:\[表\s*\d+\s*置于此处|【表\s*\d+.*?位置】)", markdown))
    if figure_count < 1 or table_count < 1:
        raise ValueError("Manuscript requires at least one marked figure position and one marked table position")
    with connect(db_path) as connection:
        connection.execute(
            """
            UPDATE module04_manuscript_runs
            SET manuscript_markdown = ?, manuscript_character_count = ?,
                evidence_ids_json = ?, figure_count = ?, table_count = ?,
                status = 'export_ready', updated_at = ?
            WHERE id = ?
            """,
            (
                markdown,
                character_count,
                json.dumps(evidence_ids, ensure_ascii=False),
                figure_count,
                table_count,
                utc_now(),
                module04_run_id,
            ),
        )
    return {
        "module04_run_id": module04_run_id,
        "status": "export_ready",
        "body_characters": character_count,
        "figure_positions": figure_count,
        "table_positions": table_count,
    }


def module04_next_action(db_path: Path, module04_run_id: str) -> dict[str, Any]:
    run = get_module04_run(db_path, module04_run_id)
    if run["status"] in {"drafting_manuscript", "manuscript_revision"}:
        module03 = get_module03_run(db_path, run["module03_run_id"])
        outline = latest_outline(db_path, run["module03_run_id"])
        return {
            "module04_run_id": module04_run_id,
            "action": "write_complete_manuscript",
            "blocking_user_input": False,
            "terminal": False,
            "must_continue": True,
            "target_characters": run["target_characters"],
            "minimum": run["min_characters"],
            "maximum": run["max_characters"],
            "selected_perspective": module03["perspective"],
            "frozen_outline": outline["outline"] if outline else None,
            "module02_run_id": module03["module02_run_id"],
            "instructions": (
                "In one root-agent writing pass, produce the complete Chinese review, preserve every frozen "
                "heading, use any relevant persisted Module 02 evidence within scope, mark figure/table "
                "positions, include references, save the Markdown, and do not send an intermediate reply."
            ),
        }
    if run["status"] == "export_ready":
        return {
            "module04_run_id": module04_run_id,
            "action": "export_markdown",
            "blocking_user_input": False,
            "terminal": False,
            "must_continue": True,
        }
    if run["status"] == "completed":
        return {
            "module04_run_id": module04_run_id,
            "action": "mvp_complete",
            "blocking_user_input": False,
            "terminal": True,
            "must_continue": False,
            "output_path": module04_export_for_run(db_path, run["module03_run_id"])["output_path"],
        }
    raise ValueError(f"Unknown Module 04 status: {run['status']}")


def export_manuscript_markdown(
    db_path: Path,
    module04_run_id: str,
    output_directory: Path,
) -> dict[str, Any]:
    run = get_module04_run(db_path, module04_run_id)
    if run["status"] != "export_ready":
        raise ValueError("Module 04 export requires a validated complete manuscript")
    content = run["manuscript_markdown"].rstrip() + "\n"
    output_directory.mkdir(parents=True, exist_ok=True)
    output_path = (output_directory / f"{module04_run_id}-review.md").resolve()
    temporary_path = output_path.with_suffix(".md.tmp")
    temporary_path.write_text(content, encoding="utf-8")
    temporary_path.replace(output_path)
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    completed_at = utc_now()
    with connect(db_path) as connection:
        existing = connection.execute(
            "SELECT id FROM module04_exports WHERE module03_run_id = ?",
            (run["module03_run_id"],),
        ).fetchone()
        export_id = str(existing["id"]) if existing else new_id("module04export")
        connection.execute(
            """
            INSERT INTO module04_exports(
                id, module03_run_id, outline_version, output_path,
                content_sha256, status, exported_at
            ) VALUES (?, ?, ?, ?, ?, 'completed', ?)
            ON CONFLICT(module03_run_id) DO UPDATE SET
                outline_version = excluded.outline_version,
                output_path = excluded.output_path,
                content_sha256 = excluded.content_sha256,
                status = 'completed', exported_at = excluded.exported_at
            """,
            (
                export_id,
                run["module03_run_id"],
                run["outline_version"],
                str(output_path),
                digest,
                completed_at,
            ),
        )
        connection.execute(
            """
            UPDATE module04_manuscript_runs
            SET status = 'completed', completed_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (completed_at, completed_at, module04_run_id),
        )
    return {
        "module04_run_id": module04_run_id,
        "module03_run_id": run["module03_run_id"],
        "output_path": str(output_path),
        "content_sha256": digest,
        "body_characters": run["manuscript_character_count"],
        "figure_positions": run["figure_count"],
        "table_positions": run["table_count"],
        "status": "completed",
        "message": "MVP任务完成",
    }


def module04_export_for_run(db_path: Path, module03_run_id: str) -> dict[str, Any] | None:
    init_module04_schema(db_path)
    with connect(db_path) as connection:
        row = connection.execute(
            "SELECT * FROM module04_exports WHERE module03_run_id = ?",
            (module03_run_id,),
        ).fetchone()
    return dict(row) if row else None
