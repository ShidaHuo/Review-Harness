from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .models import new_id, utc_now
from .module03_reporting import build_outline_markdown
from .module03_storage import get_module03_run, init_module03_schema
from .storage import connect

MODULE04_SCHEMA_SQL = """
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


def export_frozen_outline(
    db_path: Path,
    module03_run_id: str,
    output_directory: Path,
) -> dict[str, Any]:
    """Export the user-approved outline to the final Markdown artifact."""
    init_module04_schema(db_path)
    run = get_module03_run(db_path, module03_run_id)
    if run["status"] != "outline_approved":
        raise PermissionError("Module 04 requires an explicitly approved Module 03 outline")

    content, version = build_outline_markdown(
        db_path, module03_run_id, include_feedback_prompt=False
    )
    content += f"""

## 冻结状态

- 大纲版本：v{version}
- 用户决定：满意，冻结大纲
- 冻结时间：{run.get('approved_at') or '已批准'}
- MVP状态：任务完成

本文件是冻结后的综述写作大纲，不包含综述正文。
"""
    output_directory.mkdir(parents=True, exist_ok=True)
    output_path = (output_directory / f"{module03_run_id}-approved-outline-v{version:02d}.md").resolve()
    temporary_path = output_path.with_suffix(".md.tmp")
    temporary_path.write_text(content, encoding="utf-8")
    temporary_path.replace(output_path)
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    exported_at = utc_now()

    with connect(db_path) as connection:
        existing = connection.execute(
            "SELECT id FROM module04_exports WHERE module03_run_id = ?",
            (module03_run_id,),
        ).fetchone()
        export_id = str(existing["id"]) if existing else new_id("module04")
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
                status = 'completed',
                exported_at = excluded.exported_at
            """,
            (
                export_id,
                module03_run_id,
                version,
                str(output_path),
                digest,
                exported_at,
            ),
        )
    return {
        "module04_export_id": export_id,
        "module03_run_id": module03_run_id,
        "outline_version": version,
        "output_path": str(output_path),
        "content_sha256": digest,
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
