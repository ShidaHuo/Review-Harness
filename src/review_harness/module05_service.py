from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .docx_export import markdown_to_docx
from .models import new_id, utc_now
from .module03_storage import get_module03_run
from .module04_service import get_module04_run, init_module04_schema, module04_export_for_run
from .storage import connect

MODULE05_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS module05_runs (
    id TEXT PRIMARY KEY,
    module04_run_id TEXT NOT NULL UNIQUE REFERENCES module04_manuscript_runs(id),
    status TEXT NOT NULL,
    source_markdown_path TEXT NOT NULL,
    evaluation_json TEXT,
    revised_markdown TEXT,
    revised_character_count INTEGER,
    addressed_revision_ids_json TEXT NOT NULL DEFAULT '[]',
    change_log_json TEXT NOT NULL DEFAULT '[]',
    final_markdown_path TEXT,
    final_docx_path TEXT,
    final_docx_sha256 TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT
);
"""

DIMENSIONS = {"review_perspective", "differentiation", "logic", "completeness"}


def init_module05_schema(db_path: Path) -> None:
    init_module04_schema(db_path)
    with connect(db_path) as connection:
        connection.executescript(MODULE05_SCHEMA_SQL)


def start_module05_evaluation(db_path: Path, module04_run_id: str) -> str:
    init_module05_schema(db_path)
    module04 = get_module04_run(db_path, module04_run_id)
    if module04["status"] != "completed":
        raise PermissionError("Module 05 requires a completed Module 04 manuscript")
    export = module04_export_for_run(db_path, module04["module03_run_id"])
    if export is None or export["status"] != "completed":
        raise ValueError("Module 04 final Markdown export is missing")
    source_path = Path(export["output_path"])
    if not source_path.is_file():
        raise ValueError(f"Module 04 Markdown file does not exist: {source_path}")
    with connect(db_path) as connection:
        existing = connection.execute(
            "SELECT id FROM module05_runs WHERE module04_run_id = ?",
            (module04_run_id,),
        ).fetchone()
        if existing:
            return str(existing["id"])
        run_id = new_id("module05")
        now = utc_now()
        connection.execute(
            """
            INSERT INTO module05_runs(
                id, module04_run_id, status, source_markdown_path, created_at, updated_at
            ) VALUES (?, ?, 'evaluation_pending', ?, ?, ?)
            """,
            (run_id, module04_run_id, str(source_path.resolve()), now, now),
        )
    return run_id


def get_module05_run(db_path: Path, module05_run_id: str) -> dict[str, Any]:
    init_module05_schema(db_path)
    with connect(db_path) as connection:
        row = connection.execute("SELECT * FROM module05_runs WHERE id = ?", (module05_run_id,)).fetchone()
    if row is None:
        raise KeyError(f"Unknown Module 05 run: {module05_run_id}")
    result = dict(row)
    result["evaluation"] = json.loads(result.pop("evaluation_json") or "null")
    result["addressed_revision_ids"] = json.loads(result.pop("addressed_revision_ids_json") or "[]")
    result["change_log"] = json.loads(result.pop("change_log_json") or "[]")
    return result


def _validate_evaluation(module05_run_id: str, payload: dict[str, Any]) -> None:
    if payload.get("module05_run_id") != module05_run_id:
        raise ValueError("Evaluation module05_run_id does not match")
    if not str(payload.get("overall_assessment") or "").strip():
        raise ValueError("Evaluation requires an overall assessment")
    dimensions = payload.get("dimensions")
    if not isinstance(dimensions, dict) or set(dimensions) != DIMENSIONS:
        raise ValueError(f"Evaluation dimensions must be exactly {sorted(DIMENSIONS)}")
    for name, dimension in dimensions.items():
        score = dimension.get("score")
        if not isinstance(score, int) or not 1 <= score <= 5:
            raise ValueError(f"Evaluation score for {name} must be 1-5")
        if not dimension.get("evidence"):
            raise ValueError(f"Evaluation dimension {name} requires manuscript-specific evidence")
        for field in ("strengths", "weaknesses", "required_changes"):
            if not isinstance(dimension.get(field), list):
                raise ValueError(f"Evaluation dimension {name} requires {field}")
    revisions = payload.get("priority_revisions")
    if not isinstance(revisions, list) or not 1 <= len(revisions) <= 20:
        raise ValueError("Evaluation requires 1-20 concrete priority revisions")
    ids = [item.get("id") for item in revisions]
    if len(ids) != len(set(ids)) or any(re.fullmatch(r"R[1-9][0-9]*", str(item)) is None for item in ids):
        raise ValueError("Priority revision ids must be unique R1, R2, ... values")
    for item in revisions:
        for field in ("location", "problem", "change_instruction", "success_criterion"):
            if not str(item.get(field) or "").strip():
                raise ValueError(f"Priority revision {item.get('id')} requires {field}")
    if not payload.get("revision_strategy"):
        raise ValueError("Evaluation requires an ordered revision strategy")


def save_manuscript_evaluation(
    db_path: Path,
    module05_run_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    run = get_module05_run(db_path, module05_run_id)
    if run["status"] != "evaluation_pending":
        raise ValueError("Manuscript evaluation can be saved only while evaluation is pending")
    _validate_evaluation(module05_run_id, payload)
    with connect(db_path) as connection:
        connection.execute(
            """
            UPDATE module05_runs
            SET evaluation_json = ?, status = 'revision_pending', updated_at = ?
            WHERE id = ?
            """,
            (json.dumps(payload, ensure_ascii=False), utc_now(), module05_run_id),
        )
    return {
        "module05_run_id": module05_run_id,
        "status": "revision_pending",
        "priority_revision_count": len(payload["priority_revisions"]),
    }


def _plain_character_count(markdown: str) -> int:
    text = re.sub(r"[`#>*_~|\-]", "", markdown)
    text = re.sub(r"\s+", "", text)
    return len(text)


def save_revised_manuscript(
    db_path: Path,
    module05_run_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    run = get_module05_run(db_path, module05_run_id)
    if run["status"] != "revision_pending":
        raise ValueError("Revised manuscript requires a completed evaluation")
    if payload.get("module05_run_id") != module05_run_id:
        raise ValueError("Revision module05_run_id does not match")
    markdown = str(payload.get("revised_markdown") or "").strip()
    if "[@" in markdown:
        raise ValueError("Final revised manuscript must use resolved numbered citations, not internal ids")
    if len(re.findall(r"^#{1,6}\s+", markdown, flags=re.MULTILINE)) < 4:
        raise ValueError("Revised manuscript must preserve a meaningful section hierarchy")
    evaluation = run["evaluation"]
    required_ids = {item["id"] for item in evaluation["priority_revisions"]}
    addressed = set(payload.get("addressed_revision_ids", []))
    if addressed != required_ids:
        missing = sorted(required_ids - addressed)
        extra = sorted(addressed - required_ids)
        raise ValueError(f"Revision ids must address the complete evaluation (missing={missing}, extra={extra})")
    change_log = payload.get("change_log", [])
    logged = {item.get("revision_id") for item in change_log}
    if logged != required_ids:
        raise ValueError("Change log must contain one entry for every priority revision")
    source_markdown = Path(run["source_markdown_path"]).read_text(encoding="utf-8")
    source_count = _plain_character_count(source_markdown)
    revised_count = _plain_character_count(markdown)
    if revised_count < max(8_000, round(source_count * 0.75)):
        raise ValueError("Revised manuscript is too short relative to the evaluated manuscript")
    if revised_count > round(source_count * 1.5):
        raise ValueError("Revised manuscript expanded beyond the evaluation-and-revision scope")
    with connect(db_path) as connection:
        connection.execute(
            """
            UPDATE module05_runs
            SET revised_markdown = ?, revised_character_count = ?,
                addressed_revision_ids_json = ?, change_log_json = ?,
                status = 'export_ready', updated_at = ?
            WHERE id = ?
            """,
            (
                markdown,
                revised_count,
                json.dumps(sorted(addressed), ensure_ascii=False),
                json.dumps(change_log, ensure_ascii=False),
                utc_now(),
                module05_run_id,
            ),
        )
    return {
        "module05_run_id": module05_run_id,
        "status": "export_ready",
        "revised_character_count": revised_count,
        "addressed_revision_ids": sorted(addressed),
    }


def module05_next_action(db_path: Path, module05_run_id: str) -> dict[str, Any]:
    run = get_module05_run(db_path, module05_run_id)
    if run["status"] == "evaluation_pending":
        module04 = get_module04_run(db_path, run["module04_run_id"])
        module03 = get_module03_run(db_path, module04["module03_run_id"])
        with connect(db_path) as connection:
            review_rows = connection.execute(
                """
                SELECT title, review_match_level, review_reason, structure_json,
                       future_trends_json, limitations_json
                FROM module02_reviews
                WHERE module02_run_id = ? AND relevance_status = 'included'
                ORDER BY publication_date DESC, title
                """,
                (module03["module02_run_id"],),
            ).fetchall()
        prior_reviews = []
        for row in review_rows:
            item = dict(row)
            item["structure"] = json.loads(item.pop("structure_json") or "[]")
            item["future_trends"] = json.loads(item.pop("future_trends_json") or "[]")
            item["limitations"] = json.loads(item.pop("limitations_json") or "[]")
            prior_reviews.append(item)
        return {
            "module05_run_id": module05_run_id,
            "action": "evaluate_manuscript",
            "blocking_user_input": False,
            "terminal": False,
            "source_markdown_path": run["source_markdown_path"],
            "selected_perspective": module03["perspective"],
            "prior_reviews": prior_reviews,
            "criteria": [
                "review_perspective",
                "differentiation_from_prior_same_topic_reviews",
                "manuscript_logic",
                "content_completeness",
            ],
            "excluded_criteria": [
                "formatting",
                "figure_or_table_quality",
                "reference_or_citation_accuracy",
            ],
        }
    if run["status"] == "revision_pending":
        return {
            "module05_run_id": module05_run_id,
            "action": "revise_manuscript",
            "blocking_user_input": False,
            "terminal": False,
            "source_markdown_path": run["source_markdown_path"],
            "evaluation": run["evaluation"],
            "instructions": "Apply every priority revision to the concrete manuscript location and preserve claims outside the evaluation scope.",
        }
    if run["status"] == "export_ready":
        return {
            "module05_run_id": module05_run_id,
            "action": "export_final_docx",
            "blocking_user_input": False,
            "terminal": False,
        }
    if run["status"] == "completed":
        return {
            "module05_run_id": module05_run_id,
            "action": "mvp_complete",
            "blocking_user_input": False,
            "terminal": True,
            "final_docx_path": run["final_docx_path"],
        }
    raise ValueError(f"Unknown Module 05 status: {run['status']}")


def export_final_docx(
    db_path: Path,
    module05_run_id: str,
    output_directory: Path,
) -> dict[str, Any]:
    run = get_module05_run(db_path, module05_run_id)
    if run["status"] != "export_ready":
        raise ValueError("Module 05 DOCX export requires a completed manuscript revision")
    markdown = run["revised_markdown"]
    title_match = re.search(r"^#\s+(.+)$", markdown, flags=re.MULTILINE)
    title = title_match.group(1).strip() if title_match else "Final Review Manuscript"
    output_directory.mkdir(parents=True, exist_ok=True)
    markdown_path = (output_directory / f"{module05_run_id}-final-review.md").resolve()
    markdown_path.write_text(markdown.rstrip() + "\n", encoding="utf-8")
    docx_path = (output_directory / f"{module05_run_id}-final-review.docx").resolve()
    markdown_to_docx(markdown, docx_path, title=title)
    digest = hashlib.sha256(docx_path.read_bytes()).hexdigest()
    completed_at = utc_now()
    with connect(db_path) as connection:
        connection.execute(
            """
            UPDATE module05_runs
            SET final_markdown_path = ?, final_docx_path = ?, final_docx_sha256 = ?,
                status = 'completed', completed_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                str(markdown_path),
                str(docx_path),
                digest,
                completed_at,
                completed_at,
                module05_run_id,
            ),
        )
    return {
        "module05_run_id": module05_run_id,
        "status": "completed",
        "final_markdown_path": str(markdown_path),
        "final_docx_path": str(docx_path),
        "final_docx_sha256": digest,
        "message": "Module 05完成，最终DOCX已生成",
    }
