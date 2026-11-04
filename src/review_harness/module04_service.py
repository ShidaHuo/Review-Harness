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
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS module04_manuscript_sections (
    id TEXT PRIMARY KEY,
    module04_run_id TEXT NOT NULL REFERENCES module04_manuscript_runs(id),
    section_key TEXT NOT NULL,
    section_title TEXT NOT NULL,
    sort_order INTEGER NOT NULL,
    target_characters INTEGER NOT NULL,
    outline_plan_json TEXT NOT NULL,
    markdown TEXT,
    character_count INTEGER,
    cited_evidence_ids_json TEXT NOT NULL DEFAULT '[]',
    figure_placeholders_json TEXT NOT NULL DEFAULT '[]',
    table_placeholders_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'pending',
    updated_at TEXT,
    UNIQUE(module04_run_id, section_key)
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


def _plain_character_count(markdown: str) -> int:
    text = re.sub(r"\[@[^\]]+\]", "", markdown)
    text = re.sub(r"[`#>*_~|\-]", "", text)
    text = re.sub(r"\s+", "", text)
    return len(text)


def _section_plans(outline: dict[str, Any], target: int) -> list[dict[str, Any]]:
    sections = outline["sections"]
    top_levels = [item for item in sections if item["level"] == 1]
    abstract_target = max(500, round(target * 0.04))
    remaining = target - abstract_target
    weighted: list[tuple[dict[str, Any], float]] = []
    for item in top_levels:
        prefix = f"{item['number']}."
        descendants = sum(section["number"].startswith(prefix) for section in sections)
        title = item["title"].casefold()
        weight = 1.0 + 0.35 * descendants
        if "introduction" in title or "引言" in title or "绪论" in title:
            weight *= 0.75
        if any(token in title for token in ("future", "outlook", "perspective", "未来", "展望")):
            weight *= 0.9
        weighted.append((item, weight))
    weight_total = sum(weight for _, weight in weighted)
    plans = [{
        "section_key": "abstract",
        "section_title": "Abstract and Keywords",
        "sort_order": 0,
        "target_characters": abstract_target,
        "outline_plan": {
            "purpose": "Summarize the review question, scope, organizing logic, major evidence synthesis, and conclusions without adding claims beyond the manuscript.",
            "subsections": [],
        },
    }]
    allocated = abstract_target
    for index, (item, weight) in enumerate(weighted, start=1):
        section_target = round(remaining * weight / weight_total)
        if index == len(weighted):
            section_target = target - allocated
        allocated += section_target
        prefix = f"{item['number']}."
        plans.append({
            "section_key": item["number"],
            "section_title": item["title"],
            "sort_order": index,
            "target_characters": section_target,
            "outline_plan": {
                "top_level": item,
                "subsections": [
                    section for section in sections if section["number"].startswith(prefix)
                ],
            },
        })
    return plans


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
            ) VALUES (?, ?, ?, 'drafting_sections', ?, ?, ?, ?, ?)
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
        for plan in _section_plans(latest["outline"], target_characters):
            connection.execute(
                """
                INSERT INTO module04_manuscript_sections(
                    id, module04_run_id, section_key, section_title, sort_order,
                    target_characters, outline_plan_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_id("manuscriptsection"),
                    run_id,
                    plan["section_key"],
                    plan["section_title"],
                    plan["sort_order"],
                    plan["target_characters"],
                    json.dumps(plan["outline_plan"], ensure_ascii=False),
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
    return dict(row)


def _available_evidence_ids(db_path: Path, module04_run_id: str) -> set[str]:
    run = get_module04_run(db_path, module04_run_id)
    module03 = get_module03_run(db_path, run["module03_run_id"])
    module02_run_id = module03["module02_run_id"]
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
    return review_ids | paper_ids


def save_manuscript_section(
    db_path: Path,
    module04_run_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    run = get_module04_run(db_path, module04_run_id)
    if run["status"] not in {"drafting_sections", "length_revision", "visual_revision"}:
        raise ValueError("Manuscript sections can be saved only during drafting or revision")
    section_key = str(payload.get("section_key") or "").strip()
    markdown = str(payload.get("markdown") or "").strip()
    if not section_key or not markdown:
        raise ValueError("Manuscript section_key and markdown are required")
    cited_ids = list(payload.get("cited_evidence_ids", []))
    marker_ids = re.findall(r"\[@([^\]]+)\]", markdown)
    if set(marker_ids) != set(cited_ids):
        raise ValueError("Every cited evidence id must appear as [@id], with no unregistered citation markers")
    placeholders = [
        *payload.get("figure_placeholders", []),
        *payload.get("table_placeholders", []),
    ]
    for placeholder in placeholders:
        for field in ("title", "purpose", "content_spec"):
            if not str(placeholder.get(field) or "").strip():
                raise ValueError(f"Figure/table placeholder requires {field}")
        source_ids = placeholder.get("source_evidence_ids", [])
        if not isinstance(source_ids, list) or len(source_ids) != len(set(source_ids)):
            raise ValueError("Figure/table source_evidence_ids must be a unique list")
    placeholder_ids = [
        evidence_id
        for placeholder in placeholders
        for evidence_id in placeholder.get("source_evidence_ids", [])
    ]
    available = _available_evidence_ids(db_path, module04_run_id)
    unknown = (set(cited_ids) | set(placeholder_ids)) - available
    if unknown:
        raise KeyError(f"Manuscript section cites unknown evidence ids: {sorted(unknown)}")
    character_count = _plain_character_count(markdown)
    with connect(db_path) as connection:
        section = connection.execute(
            """
            SELECT id, section_title FROM module04_manuscript_sections
            WHERE module04_run_id = ? AND section_key = ?
            """,
            (module04_run_id, section_key),
        ).fetchone()
        if section is None:
            raise KeyError(f"Unknown Module 04 section key: {section_key}")
        connection.execute(
            """
            UPDATE module04_manuscript_sections
            SET markdown = ?, character_count = ?, cited_evidence_ids_json = ?,
                figure_placeholders_json = ?, table_placeholders_json = ?,
                status = 'drafted', updated_at = ?
            WHERE id = ?
            """,
            (
                markdown,
                character_count,
                json.dumps(cited_ids, ensure_ascii=False),
                json.dumps(payload.get("figure_placeholders", []), ensure_ascii=False),
                json.dumps(payload.get("table_placeholders", []), ensure_ascii=False),
                utc_now(),
                section["id"],
            ),
        )
        connection.execute(
            "UPDATE module04_manuscript_runs SET status = 'drafting_sections', updated_at = ? WHERE id = ?",
            (utc_now(), module04_run_id),
        )
    return {
        "module04_run_id": module04_run_id,
        "section_key": section_key,
        "section_title": section["section_title"],
        "character_count": character_count,
        "status": "drafted",
    }


def _section_rows(db_path: Path, module04_run_id: str) -> list[dict[str, Any]]:
    with connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT * FROM module04_manuscript_sections
            WHERE module04_run_id = ? ORDER BY sort_order
            """,
            (module04_run_id,),
        ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["outline_plan"] = json.loads(item.pop("outline_plan_json"))
        item["cited_evidence_ids"] = json.loads(item.pop("cited_evidence_ids_json") or "[]")
        item["figure_placeholders"] = json.loads(item.pop("figure_placeholders_json") or "[]")
        item["table_placeholders"] = json.loads(item.pop("table_placeholders_json") or "[]")
        result.append(item)
    return result


def module04_next_action(db_path: Path, module04_run_id: str) -> dict[str, Any]:
    run = get_module04_run(db_path, module04_run_id)
    sections = _section_rows(db_path, module04_run_id)
    if run["status"] == "completed":
        return {
            "module04_run_id": module04_run_id,
            "action": "start_module05",
            "blocking_user_input": False,
            "terminal": False,
            "must_continue": True,
        }
    pending = [section for section in sections if section["status"] != "drafted"]
    if pending:
        return {
            "module04_run_id": module04_run_id,
            "action": "draft_manuscript_sections",
            "blocking_user_input": False,
            "terminal": False,
            "must_continue": True,
            "target_total_characters": run["target_characters"],
            "sections": [
                {
                    "section_key": section["section_key"],
                    "section_title": section["section_title"],
                    "target_characters": section["target_characters"],
                    "outline_plan": section["outline_plan"],
                }
                for section in pending
            ],
            "required_completion": "Persist every returned section before any user-visible reply.",
            "instructions": "Draft every returned section in Chinese, use [@evidence_id] internally for citations, supply figure/table position specifications separately, import each section, and call module04-next again without replying to the user.",
        }
    figure_count = sum(len(section["figure_placeholders"]) for section in sections)
    table_count = sum(len(section["table_placeholders"]) for section in sections)
    if figure_count == 0 or table_count == 0:
        with connect(db_path) as connection:
            connection.execute(
                "UPDATE module04_manuscript_runs SET status = 'visual_revision', updated_at = ? WHERE id = ?",
                (utc_now(), module04_run_id),
            )
        return {
            "module04_run_id": module04_run_id,
            "action": "add_figure_table_positions",
            "blocking_user_input": False,
            "terminal": False,
            "must_continue": True,
            "missing": [
                kind for kind, count in (("figure", figure_count), ("table", table_count))
                if count == 0
            ],
            "instructions": "Re-import appropriate drafted sections with at least one evidence-grounded figure position and one table position.",
        }
    total = sum(int(section["character_count"] or 0) for section in sections)
    if not run["min_characters"] <= total <= run["max_characters"]:
        with connect(db_path) as connection:
            connection.execute(
                "UPDATE module04_manuscript_runs SET status = 'length_revision', updated_at = ? WHERE id = ?",
                (utc_now(), module04_run_id),
            )
        return {
            "module04_run_id": module04_run_id,
            "action": "revise_manuscript_length",
            "blocking_user_input": False,
            "terminal": False,
            "must_continue": True,
            "target_characters": run["target_characters"],
            "minimum": run["min_characters"],
            "maximum": run["max_characters"],
            "actual": total,
            "sections": [
                {
                    "section_key": section["section_key"],
                    "target": section["target_characters"],
                    "actual": section["character_count"],
                }
                for section in sections
            ],
        }
    return {
        "module04_run_id": module04_run_id,
        "action": "assemble_manuscript",
        "blocking_user_input": False,
        "terminal": False,
        "must_continue": True,
        "actual_characters": total,
    }


def _evidence_reference(db_path: Path, module02_run_id: str, evidence_id: str) -> str:
    with connect(db_path) as connection:
        review = connection.execute(
            """
            SELECT title, journal, publication_year, doi, paper_url
            FROM module02_reviews WHERE module02_run_id = ? AND id = ?
            """,
            (module02_run_id, evidence_id),
        ).fetchone()
        if review:
            link = f"https://doi.org/{review['doi']}" if review["doi"] else review["paper_url"]
            venue = review["journal"] or "venue unavailable"
            return f"{review['title']}. {venue}, {review['publication_year']}. {link}"
        paper = connection.execute(
            """
            SELECT p.title, p.source_name, p.publication_year, p.doi, p.openalex_id
            FROM module02_research mr JOIN papers p ON p.id = mr.paper_id
            WHERE mr.module02_run_id = ? AND mr.paper_id = ?
            """,
            (module02_run_id, evidence_id),
        ).fetchone()
        if paper:
            link = f"https://doi.org/{paper['doi']}" if paper["doi"] else paper["openalex_id"]
            venue = paper["source_name"] or "venue unavailable"
            return f"{paper['title']}. {venue}, {paper['publication_year']}. {link}"
    raise KeyError(f"Cannot resolve manuscript reference: {evidence_id}")


def assemble_manuscript(
    db_path: Path,
    module04_run_id: str,
    output_directory: Path,
) -> dict[str, Any]:
    run = get_module04_run(db_path, module04_run_id)
    next_action = module04_next_action(db_path, module04_run_id)
    if next_action["action"] != "assemble_manuscript":
        raise ValueError(f"Module 04 is not ready to assemble: {next_action['action']}")
    module03 = get_module03_run(db_path, run["module03_run_id"])
    outline = latest_outline(db_path, run["module03_run_id"])
    if outline is None:
        raise ValueError("Approved outline is missing")
    sections = _section_rows(db_path, module04_run_id)
    citation_order: list[str] = []
    for section in sections:
        for evidence_id in section["cited_evidence_ids"]:
            if evidence_id not in citation_order:
                citation_order.append(evidence_id)
        for placeholder in [*section["figure_placeholders"], *section["table_placeholders"]]:
            for evidence_id in placeholder.get("source_evidence_ids", []):
                if evidence_id not in citation_order:
                    citation_order.append(evidence_id)
    citation_numbers = {evidence_id: index for index, evidence_id in enumerate(citation_order, start=1)}

    parts = [f"# {outline['outline']['candidate_title']}\n"]
    figure_number = 0
    table_number = 0
    for section in sections:
        markdown = section["markdown"] or ""
        for evidence_id, number in citation_numbers.items():
            markdown = markdown.replace(f"[@{evidence_id}]", f"[{number}]")
        parts.append(markdown.strip())
        for placeholder in section["figure_placeholders"]:
            figure_number += 1
            source_numbers = [citation_numbers[item] for item in placeholder.get("source_evidence_ids", [])]
            sources = ", ".join(f"[{number}]" for number in source_numbers) or "由正文综合"
            parts.append(
                f"> **[图 {figure_number} 置于此处：{placeholder['title']}]**  \n"
                f"> 用途：{placeholder['purpose']}  \n"
                f"> 建议内容：{placeholder['content_spec']}  \n"
                f"> 证据来源：{sources}"
            )
        for placeholder in section["table_placeholders"]:
            table_number += 1
            source_numbers = [citation_numbers[item] for item in placeholder.get("source_evidence_ids", [])]
            sources = ", ".join(f"[{number}]" for number in source_numbers) or "由正文综合"
            parts.append(
                f"> **[表 {table_number} 置于此处：{placeholder['title']}]**  \n"
                f"> 用途：{placeholder['purpose']}  \n"
                f"> 建议列项：{placeholder['content_spec']}  \n"
                f"> 证据来源：{sources}"
            )
    if citation_order:
        references = ["## 参考文献"]
        references.extend(
            f"{index}. {_evidence_reference(db_path, module03['module02_run_id'], evidence_id)}"
            for index, evidence_id in enumerate(citation_order, start=1)
        )
        parts.append("\n".join(references))
    body_characters = sum(int(section["character_count"] or 0) for section in sections)
    parts.append(
        f"## 稿件状态\n\n"
        f"- 冻结大纲版本：v{run['outline_version']}\n"
        f"- 正文字数口径：去除空白和Markdown标记后约{body_characters}字\n"
        f"- 图位置标记：{figure_number}处\n"
        f"- 表位置标记：{table_number}处\n"
        f"- Module 04状态：Markdown稿件完成，待Module 05评价与修订"
    )
    content = "\n\n".join(parts).strip() + "\n"
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
        "body_characters": body_characters,
        "figure_placeholders": figure_number,
        "table_placeholders": table_number,
        "status": "completed",
        "message": "Module 04完成，进入Module 05评价与修订",
    }


def module04_export_for_run(db_path: Path, module03_run_id: str) -> dict[str, Any] | None:
    init_module04_schema(db_path)
    with connect(db_path) as connection:
        row = connection.execute(
            "SELECT * FROM module04_exports WHERE module03_run_id = ?",
            (module03_run_id,),
        ).fetchone()
    return dict(row) if row else None
