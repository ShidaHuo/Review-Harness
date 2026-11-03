from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .models import MAX_TOPIC_SEARCHES, SEARCH_QUERY_LIMITS, new_id, utc_now
from .query_plans import (
    canonicalize_query_plan,
    normalize_topic_key,
    query_by_id,
    query_plan_sha256,
)

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS canonical_query_plans (
    id TEXT PRIMARY KEY,
    topic_key TEXT NOT NULL UNIQUE,
    plan_json TEXT NOT NULL,
    plan_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS topic_runs (
    id TEXT PRIMARY KEY,
    topic TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'collecting',
    profile_json TEXT NOT NULL,
    query_plan_id TEXT REFERENCES canonical_query_plans(id),
    query_plan_sha256 TEXT,
    skill_version TEXT NOT NULL,
    agent_recommendation TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS search_runs (
    id TEXT PRIMARY KEY,
    topic_run_id TEXT NOT NULL REFERENCES topic_runs(id),
    provider TEXT NOT NULL,
    query_id TEXT,
    scope TEXT NOT NULL,
    query TEXT NOT NULL,
    from_date TEXT NOT NULL,
    to_date TEXT NOT NULL,
    max_pages INTEGER NOT NULL,
    raw_directory TEXT NOT NULL,
    status TEXT NOT NULL,
    records_received INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    started_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS papers (
    id TEXT PRIMARY KEY,
    openalex_id TEXT,
    doi TEXT,
    title TEXT NOT NULL,
    normalized_title TEXT NOT NULL,
    abstract TEXT,
    publication_date TEXT,
    publication_year INTEGER NOT NULL,
    work_type TEXT NOT NULL,
    source_name TEXT,
    issn_l TEXT,
    cited_by_count INTEGER,
    source_provider TEXT NOT NULL,
    retrieved_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_papers_openalex_id
    ON papers(openalex_id) WHERE openalex_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_papers_doi
    ON papers(doi) WHERE doi IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_papers_title_year
    ON papers(normalized_title, publication_year);

CREATE TABLE IF NOT EXISTS run_papers (
    topic_run_id TEXT NOT NULL REFERENCES topic_runs(id),
    paper_id TEXT NOT NULL REFERENCES papers(id),
    search_run_id TEXT NOT NULL REFERENCES search_runs(id),
    retrieval_scope TEXT NOT NULL,
    relevance_label TEXT,
    relevance_confidence TEXT,
    relevance_reason TEXT,
    classified_by TEXT,
    classified_at TEXT,
    PRIMARY KEY(topic_run_id, paper_id, search_run_id)
);

CREATE TABLE IF NOT EXISTS assessments (
    id TEXT PRIMARY KEY,
    topic_run_id TEXT NOT NULL REFERENCES topic_runs(id),
    assessment_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS decisions (
    id TEXT PRIMARY KEY,
    topic_run_id TEXT NOT NULL REFERENCES topic_runs(id),
    agent_recommendation TEXT NOT NULL,
    user_decision TEXT NOT NULL,
    module_02_permitted INTEGER NOT NULL,
    notes TEXT,
    decided_at TEXT NOT NULL
);
"""


@contextmanager
def connect(db_path: Path) -> Iterator[sqlite3.Connection]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
    except Exception:
        connection.rollback()
        raise
    else:
        connection.commit()
    finally:
        connection.close()


def init_db(db_path: Path) -> None:
    with connect(db_path) as connection:
        connection.executescript(SCHEMA_SQL)
        topic_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(topic_runs)")
        }
        if "query_plan_id" not in topic_columns:
            connection.execute("ALTER TABLE topic_runs ADD COLUMN query_plan_id TEXT")
        if "query_plan_sha256" not in topic_columns:
            connection.execute("ALTER TABLE topic_runs ADD COLUMN query_plan_sha256 TEXT")
        search_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(search_runs)")
        }
        if "query_id" not in search_columns:
            connection.execute("ALTER TABLE search_runs ADD COLUMN query_id TEXT")

        # Seed one canonical plan per existing topic without rewriting historical runs.
        rows = connection.execute(
            "SELECT id, topic, profile_json FROM topic_runs ORDER BY created_at, id"
        ).fetchall()
        for row in rows:
            profile = json.loads(row["profile_json"])
            try:
                plan = canonicalize_query_plan(profile.get("queries", []))
            except ValueError:
                continue
            topic_key = normalize_topic_key(row["topic"], profile)
            digest = query_plan_sha256(plan)
            existing = connection.execute(
                "SELECT id, plan_sha256 FROM canonical_query_plans WHERE topic_key = ?",
                (topic_key,),
            ).fetchone()
            if existing is None:
                plan_id = new_id("queryplan")
                connection.execute(
                    """
                    INSERT INTO canonical_query_plans(id, topic_key, plan_json, plan_sha256, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (plan_id, topic_key, json.dumps(plan, ensure_ascii=False), digest, utc_now()),
                )
            elif existing["plan_sha256"] == digest:
                plan_id = str(existing["id"])
            else:
                continue
            connection.execute(
                """
                UPDATE topic_runs SET query_plan_id = ?, query_plan_sha256 = ?
                WHERE id = ? AND query_plan_id IS NULL
                """,
                (plan_id, digest, row["id"]),
            )


def create_or_resume_topic_run(
    db_path: Path,
    topic: str,
    profile: dict[str, Any],
    skill_version: str = "0.7.3",
) -> tuple[str, bool]:
    """Reuse the newest unfinished run for the same normalized topic."""
    init_db(db_path)
    topic_key = normalize_topic_key(topic, profile)
    with connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT id, topic, status, profile_json FROM topic_runs
            ORDER BY created_at DESC, id DESC
            """
        ).fetchall()
    for row in rows:
        existing_profile = json.loads(row["profile_json"])
        if normalize_topic_key(row["topic"], existing_profile) != topic_key:
            continue
        if row["status"] == "collecting":
            return str(row["id"]), True
        # A newer completed run closes any older abandoned run for this topic.
        break
    return create_topic_run(db_path, topic, profile, skill_version), False


def create_topic_run(db_path: Path, topic: str, profile: dict[str, Any], skill_version: str = "0.7.3") -> str:
    init_db(db_path)
    topic_key = normalize_topic_key(topic, profile)
    supplied_plan = canonicalize_query_plan(profile.get("queries", []))
    with connect(db_path) as connection:
        canonical = connection.execute(
            "SELECT id, plan_json, plan_sha256 FROM canonical_query_plans WHERE topic_key = ?",
            (topic_key,),
        ).fetchone()
        if canonical is None:
            plan = supplied_plan
            plan_id = new_id("queryplan")
            digest = query_plan_sha256(plan)
            connection.execute(
                """
                INSERT INTO canonical_query_plans(id, topic_key, plan_json, plan_sha256, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (plan_id, topic_key, json.dumps(plan, ensure_ascii=False), digest, utc_now()),
            )
        else:
            plan = json.loads(canonical["plan_json"])
            plan_id = str(canonical["id"])
            digest = str(canonical["plan_sha256"])

        frozen_profile = json.loads(json.dumps(profile, ensure_ascii=False))
        frozen_profile["queries"] = plan
        run_id = new_id("topic")
        now = utc_now()
        connection.execute(
            """
            INSERT INTO topic_runs(
                id, topic, profile_json, query_plan_id, query_plan_sha256,
                skill_version, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                topic,
                json.dumps(frozen_profile, ensure_ascii=False, sort_keys=True),
                plan_id,
                digest,
                skill_version,
                now,
                now,
            ),
        )
    return run_id


def frozen_query_for_run(db_path: Path, run_id: str, query_id: str) -> dict[str, Any]:
    run = get_topic_run(db_path, run_id)
    return query_by_id(run["profile"].get("queries", []), query_id)


def get_topic_run(db_path: Path, run_id: str) -> dict[str, Any]:
    with connect(db_path) as connection:
        row = connection.execute("SELECT * FROM topic_runs WHERE id = ?", (run_id,)).fetchone()
    if row is None:
        raise KeyError(f"Unknown topic run: {run_id}")
    result = dict(row)
    result["profile"] = json.loads(result.pop("profile_json"))
    return result


def start_search_run(
    db_path: Path,
    *,
    topic_run_id: str,
    query_id: str,
    from_date: str,
    to_date: str,
    max_pages: int,
    raw_directory: Path,
) -> str:
    frozen = frozen_query_for_run(db_path, topic_run_id, query_id)
    scope = frozen["scope"]
    query = frozen["query"]
    search_run_id = new_id("search")
    with connect(db_path) as connection:
        total_count = connection.execute(
            "SELECT COUNT(*) FROM search_runs WHERE topic_run_id = ?",
            (topic_run_id,),
        ).fetchone()[0]
        scope_count = connection.execute(
            "SELECT COUNT(*) FROM search_runs WHERE topic_run_id = ? AND scope = ?",
            (topic_run_id, scope),
        ).fetchone()[0]
        duplicate = connection.execute(
            "SELECT 1 FROM search_runs WHERE topic_run_id = ? AND query_id = ? LIMIT 1",
            (topic_run_id, query_id),
        ).fetchone()
        if total_count >= MAX_TOPIC_SEARCHES:
            raise ValueError(f"Module 01 allows at most {MAX_TOPIC_SEARCHES} searches per topic")
        if scope_count >= SEARCH_QUERY_LIMITS[scope]:
            raise ValueError(
                f"Module 01 allows at most {SEARCH_QUERY_LIMITS[scope]} {scope} searches per topic"
            )
        if duplicate:
            raise ValueError("This frozen query id has already been attempted")
        connection.execute(
            """
            INSERT INTO search_runs(
                id, topic_run_id, provider, query_id, scope, query, from_date, to_date,
                max_pages, raw_directory, status, started_at
            ) VALUES (?, ?, 'openalex', ?, ?, ?, ?, ?, ?, ?, 'running', ?)
            """,
            (
                search_run_id,
                topic_run_id,
                query_id,
                scope,
                query,
                from_date,
                to_date,
                max_pages,
                str(raw_directory),
                utc_now(),
            ),
        )
    return search_run_id


def set_search_raw_directory(db_path: Path, search_run_id: str, raw_directory: Path) -> None:
    with connect(db_path) as connection:
        connection.execute(
            "UPDATE search_runs SET raw_directory = ? WHERE id = ?",
            (str(raw_directory), search_run_id),
        )


def finish_search_run(db_path: Path, search_run_id: str, *, records_received: int, error: str | None = None) -> None:
    with connect(db_path) as connection:
        connection.execute(
            """
            UPDATE search_runs
            SET status = ?, records_received = ?, error = ?, completed_at = ?
            WHERE id = ?
            """,
            ("failed" if error else "completed", records_received, error, utc_now(), search_run_id),
        )


def _find_existing_paper(connection: sqlite3.Connection, paper: dict[str, Any]) -> str | None:
    if paper.get("openalex_id"):
        row = connection.execute("SELECT id FROM papers WHERE openalex_id = ?", (paper["openalex_id"],)).fetchone()
        if row:
            return str(row["id"])
    if paper.get("doi"):
        row = connection.execute("SELECT id FROM papers WHERE doi = ?", (paper["doi"],)).fetchone()
        if row:
            return str(row["id"])
    row = connection.execute(
        "SELECT id FROM papers WHERE normalized_title = ? AND publication_year = ? LIMIT 1",
        (paper["normalized_title"], paper["publication_year"]),
    ).fetchone()
    return str(row["id"]) if row else None


def upsert_and_link_paper(
    db_path: Path,
    *,
    topic_run_id: str,
    search_run_id: str,
    scope: str,
    paper: dict[str, Any],
) -> tuple[str, bool]:
    with connect(db_path) as connection:
        existing_id = _find_existing_paper(connection, paper)
        paper_id = existing_id or paper["paper_id"]
        is_new = existing_id is None
        if is_new:
            connection.execute(
                """
                INSERT INTO papers(
                    id, openalex_id, doi, title, normalized_title, abstract,
                    publication_date, publication_year, work_type, source_name,
                    issn_l, cited_by_count, source_provider, retrieved_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    paper_id,
                    paper.get("openalex_id"),
                    paper.get("doi"),
                    paper["title"],
                    paper["normalized_title"],
                    paper.get("abstract"),
                    paper.get("publication_date"),
                    paper["publication_year"],
                    paper["work_type"],
                    paper.get("source_name"),
                    paper.get("issn_l"),
                    paper.get("cited_by_count"),
                    paper["source_provider"],
                    paper["retrieved_at"],
                ),
            )
        connection.execute(
            """
            INSERT OR IGNORE INTO run_papers(topic_run_id, paper_id, search_run_id, retrieval_scope)
            VALUES (?, ?, ?, ?)
            """,
            (topic_run_id, paper_id, search_run_id, scope),
        )
    return paper_id, is_new


def status_for_run(db_path: Path, run_id: str) -> dict[str, Any]:
    run = get_topic_run(db_path, run_id)
    with connect(db_path) as connection:
        search_rows = connection.execute(
            """
            SELECT id, provider, query_id, scope, query, from_date, to_date, raw_directory, status,
                   records_received, error, started_at, completed_at
            FROM search_runs WHERE topic_run_id = ? ORDER BY started_at
            """,
            (run_id,),
        ).fetchall()
        scope_rows = connection.execute(
            """
            SELECT retrieval_scope, COUNT(DISTINCT paper_id) AS paper_count
            FROM run_papers WHERE topic_run_id = ? GROUP BY retrieval_scope
            """,
            (run_id,),
        ).fetchall()
        relevance_rows = connection.execute(
            """
            SELECT relevance_label, COUNT(DISTINCT paper_id) AS paper_count
            FROM run_papers
            WHERE topic_run_id = ? AND relevance_label IS NOT NULL
            GROUP BY relevance_label
            """,
            (run_id,),
        ).fetchall()
        decision = connection.execute(
            "SELECT * FROM decisions WHERE topic_run_id = ? ORDER BY decided_at DESC LIMIT 1",
            (run_id,),
        ).fetchone()
    return {
        "run": run,
        "searches": [dict(row) for row in search_rows],
        "paper_counts_by_retrieval_scope": {row["retrieval_scope"]: row["paper_count"] for row in scope_rows},
        "paper_counts_by_relevance": {row["relevance_label"]: row["paper_count"] for row in relevance_rows},
        "latest_decision": dict(decision) if decision else None,
    }


def save_decision(db_path: Path, run_id: str, decision: str, notes: str | None = None) -> dict[str, Any]:
    run = get_topic_run(db_path, run_id)
    if decision == "approved":
        planned = run["profile"].get("queries", [])
        with connect(db_path) as connection:
            searches = connection.execute(
                "SELECT query_id, scope, query FROM search_runs WHERE topic_run_id = ?",
                (run_id,),
            ).fetchall()
            attempted_ids = {row["query_id"] for row in searches if row["query_id"]}
            attempted_legacy = {(row["scope"], row["query"]) for row in searches}
            missing = [
                item["id"] for item in planned
                if item["id"] not in attempted_ids
                and (item["scope"], item["query"]) not in attempted_legacy
            ]
            pending = connection.execute(
                """
                SELECT COUNT(DISTINCT paper_id) FROM run_papers
                WHERE topic_run_id = ? AND relevance_label IS NULL
                """,
                (run_id,),
            ).fetchone()[0]
        if missing:
            raise ValueError(f"Cannot approve Module 01 before frozen queries are attempted: {missing}")
        if pending:
            raise ValueError(f"Cannot approve Module 01: {pending} papers remain semantically unclassified")
    decided_at = utc_now()
    record = {
        "id": new_id("decision"),
        "topic_run_id": run_id,
        "agent_recommendation": run["agent_recommendation"],
        "user_decision": decision,
        "module_02_permitted": decision == "approved",
        "notes": notes,
        "decided_at": decided_at,
    }
    with connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO decisions(
                id, topic_run_id, agent_recommendation, user_decision,
                module_02_permitted, notes, decided_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["id"],
                record["topic_run_id"],
                record["agent_recommendation"],
                record["user_decision"],
                int(record["module_02_permitted"]),
                record["notes"],
                record["decided_at"],
            ),
        )
        connection.execute(
            "UPDATE topic_runs SET status = ?, updated_at = ? WHERE id = ?",
            ("approved" if decision == "approved" else decision, decided_at, run_id),
        )
    return record


def save_module01_relevance(db_path: Path, run_id: str, papers: list[dict[str, Any]]) -> int:
    valid_labels = {"direct", "technical", "excluded", "uncertain"}
    valid_confidence = {"low", "medium", "high"}
    updated = 0
    with connect(db_path) as connection:
        for paper in papers:
            if paper["label"] not in valid_labels:
                raise ValueError(f"Invalid Module 01 relevance label: {paper['label']}")
            if paper["confidence"] not in valid_confidence:
                raise ValueError(f"Invalid Module 01 relevance confidence: {paper['confidence']}")
            exists = connection.execute(
                """
                SELECT 1 FROM run_papers
                WHERE topic_run_id = ? AND paper_id = ? LIMIT 1
                """,
                (run_id, paper["paper_id"]),
            ).fetchone()
            if exists is None:
                raise KeyError(f"Paper is not linked to this Module 01 run: {paper['paper_id']}")
            connection.execute(
                """
                UPDATE run_papers
                SET relevance_label = ?, relevance_confidence = ?, relevance_reason = ?,
                    classified_by = ?, classified_at = ?
                WHERE topic_run_id = ? AND paper_id = ?
                """,
                (
                    paper["label"],
                    paper["confidence"],
                    paper["reason"],
                    paper["actor"],
                    utc_now(),
                    run_id,
                    paper["paper_id"],
                ),
            )
            updated += 1
    return updated


def export_module01_papers(db_path: Path, run_id: str) -> list[dict[str, Any]]:
    """Export one deduplicated title/abstract record per Module 01 paper."""
    get_topic_run(db_path, run_id)
    with connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT p.*, GROUP_CONCAT(DISTINCT rp.retrieval_scope) AS retrieval_scopes,
                   MAX(rp.relevance_label) AS relevance_label,
                   MAX(rp.relevance_confidence) AS relevance_confidence,
                   MAX(rp.relevance_reason) AS relevance_reason
            FROM papers p
            JOIN run_papers rp ON rp.paper_id = p.id
            WHERE rp.topic_run_id = ?
            GROUP BY p.id
            ORDER BY p.publication_date DESC, p.title
            """,
            (run_id,),
        ).fetchall()
    results: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["retrieval_scopes"] = sorted((item.pop("retrieval_scopes") or "").split(","))
        results.append(item)
    return results


def module01_next_action(db_path: Path, run_id: str) -> dict[str, Any]:
    """Return the next mandatory Module 01 step for every supported runtime."""
    status = status_for_run(db_path, run_id)
    run = status["run"]
    decision = status.get("latest_decision")
    if decision is not None:
        if decision["user_decision"] == "approved":
            return {
                "run_id": run_id,
                "action": "start_module02",
                "blocking_user_input": False,
                "terminal": False,
            }
        return {
            "run_id": run_id,
            "action": "module01_complete",
            "blocking_user_input": False,
            "terminal": True,
            "decision": decision["user_decision"],
        }

    planned = run["profile"].get("queries", [])
    attempted_ids = {item.get("query_id") for item in status["searches"] if item.get("query_id")}
    attempted_legacy = {(item["scope"], item["query"]) for item in status["searches"]}
    missing = [
        item for item in planned
        if item["id"] not in attempted_ids
        and (item["scope"], item["query"]) not in attempted_legacy
    ]
    if missing:
        return {
            "run_id": run_id,
            "action": "search_literature",
            "blocking_user_input": False,
            "terminal": False,
            "queries": [
                {"id": item["id"], "scope": item["scope"]}
                for item in missing
            ],
        }

    running = [item["query_id"] or item["query"] for item in status["searches"] if item["status"] == "running"]
    if running:
        return {
            "run_id": run_id,
            "action": "wait_for_search_completion",
            "blocking_user_input": False,
            "terminal": False,
            "queries": running,
        }

    papers = export_module01_papers(db_path, run_id)
    pending = [item for item in papers if item.get("relevance_label") is None]
    if pending:
        return {
            "run_id": run_id,
            "action": "screen_papers",
            "blocking_user_input": False,
            "terminal": False,
            "paper_count": len(pending),
            "recommended_batch_size": 25,
            "export_command": f"export-module01-papers --run-id {run_id} --output <path>",
        }

    failed_or_capped = [
        {
            "query_id": item.get("query_id"),
            "status": item["status"],
            "records_received": item["records_received"],
            "limited": item["status"] != "completed" or item["records_received"] >= 50,
        }
        for item in status["searches"]
        if item["status"] != "completed" or item["records_received"] >= 50
    ]
    return {
        "run_id": run_id,
        "action": "synthesize_report_and_collect_decision",
        "blocking_user_input": True,
        "terminal": False,
        "paper_count": len(papers),
        "retrieval_limitations": failed_or_capped,
        "decision_prompt": ["1. 继续", "2. 结束"],
    }
