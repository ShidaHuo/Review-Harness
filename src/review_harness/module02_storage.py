from __future__ import annotations

import calendar
import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from .models import RESEARCH_WORK_TYPES, new_id, rolling_two_year_window, utc_now
from .query_plans import build_review_query_plan, query_by_id, review_query_plan_sha256
from .reference_storage import nature_index_snapshot_for_topic
from .storage import connect, get_topic_run, init_db

MODULE02_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS module02_runs (
    id TEXT PRIMARY KEY,
    topic_run_id TEXT NOT NULL UNIQUE REFERENCES topic_runs(id),
    status TEXT NOT NULL,
    newest_review_id TEXT,
    newest_review_date TEXT,
    trend_baseline_review_id TEXT,
    trend_baseline_review_date TEXT,
    nature_index_snapshot_id TEXT,
    review_query_plan_json TEXT,
    review_query_plan_sha256 TEXT,
    trend_claims_finalized INTEGER NOT NULL DEFAULT 0,
    research_comparison_finalized INTEGER NOT NULL DEFAULT 0,
    research_from_date TEXT,
    research_to_date TEXT,
    perspectives_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS module02_searches (
    id TEXT PRIMARY KEY,
    module02_run_id TEXT NOT NULL REFERENCES module02_runs(id),
    phase TEXT NOT NULL,
    query_id TEXT,
    scope TEXT NOT NULL,
    query TEXT NOT NULL,
    from_date TEXT,
    to_date TEXT,
    work_type_filter TEXT,
    raw_directory TEXT NOT NULL,
    status TEXT NOT NULL,
    records_received INTEGER NOT NULL DEFAULT 0,
    records_retained INTEGER NOT NULL DEFAULT 0,
    provider_total INTEGER,
    truncated INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    started_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS module02_reviews (
    id TEXT PRIMARY KEY,
    module02_run_id TEXT NOT NULL REFERENCES module02_runs(id),
    openalex_id TEXT,
    doi TEXT,
    title TEXT NOT NULL,
    normalized_title TEXT NOT NULL,
    abstract TEXT,
    publication_date TEXT,
    publication_year INTEGER NOT NULL,
    journal TEXT,
    issn_l TEXT,
    cited_by_count INTEGER,
    citation_as_of TEXT NOT NULL,
    paper_url TEXT NOT NULL,
    provider_work_type TEXT,
    fulltext_access_status TEXT NOT NULL DEFAULT 'not_checked',
    fulltext_source_url TEXT,
    pdf_path TEXT,
    pdf_sha256 TEXT,
    fulltext_license TEXT,
    fulltext_note TEXT,
    fulltext_checked_at TEXT,
    nature_index_status TEXT NOT NULL DEFAULT 'unverified',
    relevance_status TEXT NOT NULL DEFAULT 'pending',
    review_match_level TEXT,
    review_relevance_score REAL,
    matched_keywords_json TEXT,
    screening_confidence TEXT,
    screening_reason TEXT,
    screened_at TEXT,
    evidence_level TEXT,
    review_reason TEXT,
    structure_json TEXT,
    future_trends_json TEXT,
    source_urls_json TEXT,
    limitations_json TEXT,
    analyzed_at TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_module02_reviews_openalex
    ON module02_reviews(module02_run_id, openalex_id) WHERE openalex_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_module02_reviews_doi
    ON module02_reviews(module02_run_id, doi) WHERE doi IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_module02_reviews_title_year
    ON module02_reviews(module02_run_id, normalized_title, publication_year);

CREATE TABLE IF NOT EXISTS module02_research (
    module02_run_id TEXT NOT NULL REFERENCES module02_runs(id),
    paper_id TEXT NOT NULL REFERENCES papers(id),
    origin TEXT NOT NULL,
    scope TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'pending',
    matched_review_ids_json TEXT NOT NULL DEFAULT '[]',
    matched_trend_claim_ids_json TEXT NOT NULL DEFAULT '[]',
    matched_future_trends_json TEXT NOT NULL DEFAULT '[]',
    rationale TEXT,
    confidence TEXT,
    classified_at TEXT,
    PRIMARY KEY(module02_run_id, paper_id)
);

CREATE TABLE IF NOT EXISTS module02_trend_claims (
    id TEXT NOT NULL,
    module02_run_id TEXT NOT NULL REFERENCES module02_runs(id),
    canonical_label TEXT NOT NULL,
    description TEXT NOT NULL,
    source_review_ids_json TEXT NOT NULL,
    source_statements_json TEXT NOT NULL,
    scope_note TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY(module02_run_id, id)
);

CREATE TABLE IF NOT EXISTS module03_perspective_branches (
    id TEXT PRIMARY KEY,
    module02_run_id TEXT NOT NULL REFERENCES module02_runs(id),
    perspective_rank INTEGER NOT NULL,
    perspective_title TEXT NOT NULL,
    perspective_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'available',
    dsh_session_id TEXT,
    created_at TEXT NOT NULL,
    selected_at TEXT,
    UNIQUE(module02_run_id, perspective_rank),
    UNIQUE(dsh_session_id)
);
"""

REVIEW_QUERY_LIMIT = 4
RESEARCH_QUERY_LIMITS = {"direct": 3, "technical": 3}


def init_module02_schema(db_path: Path) -> None:
    init_db(db_path)
    with connect(db_path) as connection:
        connection.executescript(MODULE02_SCHEMA_SQL)
        existing_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(module02_reviews)")
        }
        migrations = {
            "fulltext_access_status": "TEXT NOT NULL DEFAULT 'not_checked'",
            "provider_work_type": "TEXT",
            "fulltext_source_url": "TEXT",
            "pdf_path": "TEXT",
            "pdf_sha256": "TEXT",
            "fulltext_license": "TEXT",
            "fulltext_note": "TEXT",
            "fulltext_checked_at": "TEXT",
            "review_match_level": "TEXT",
            "review_relevance_score": "REAL",
            "matched_keywords_json": "TEXT",
            "screening_confidence": "TEXT",
            "screening_reason": "TEXT",
            "screened_at": "TEXT",
        }
        for column, declaration in migrations.items():
            if column not in existing_columns:
                connection.execute(
                    f"ALTER TABLE module02_reviews ADD COLUMN {column} {declaration}"
                )

        run_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(module02_runs)")
        }
        run_migrations = {
            "trend_baseline_review_id": "TEXT",
            "trend_baseline_review_date": "TEXT",
            "nature_index_snapshot_id": "TEXT",
            "review_query_plan_json": "TEXT",
            "review_query_plan_sha256": "TEXT",
            "trend_claims_finalized": "INTEGER NOT NULL DEFAULT 0",
            "research_comparison_finalized": "INTEGER NOT NULL DEFAULT 0",
        }
        for column, declaration in run_migrations.items():
            if column not in run_columns:
                connection.execute(f"ALTER TABLE module02_runs ADD COLUMN {column} {declaration}")

        search_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(module02_searches)")
        }
        if "query_id" not in search_columns:
            connection.execute("ALTER TABLE module02_searches ADD COLUMN query_id TEXT")

        research_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(module02_research)")
        }
        if "matched_trend_claim_ids_json" not in research_columns:
            connection.execute(
                "ALTER TABLE module02_research ADD COLUMN matched_trend_claim_ids_json TEXT NOT NULL DEFAULT '[]'"
            )

        rows = connection.execute(
            """
            SELECT m.id, t.profile_json
            FROM module02_runs m
            JOIN topic_runs t ON t.id = m.topic_run_id
            WHERE m.review_query_plan_json IS NULL
            """
        ).fetchall()
        for row in rows:
            profile = json.loads(row["profile_json"])
            try:
                review_plan = build_review_query_plan(profile.get("queries", []))
            except ValueError:
                continue
            connection.execute(
                """
                UPDATE module02_runs
                SET review_query_plan_json = ?, review_query_plan_sha256 = ?
                WHERE id = ?
                """,
                (
                    json.dumps(review_plan, ensure_ascii=False),
                    review_query_plan_sha256(review_plan),
                    row["id"],
                ),
            )


def create_module02_run(db_path: Path, topic_run_id: str) -> str:
    init_module02_schema(db_path)
    topic_run = get_topic_run(db_path, topic_run_id)
    nature_snapshot = nature_index_snapshot_for_topic(db_path, topic_run_id)
    nature_snapshot_id = nature_snapshot["id"] if nature_snapshot else None
    review_plan = build_review_query_plan(topic_run["profile"].get("queries", []))
    review_plan_json = json.dumps(review_plan, ensure_ascii=False)
    review_plan_hash = review_query_plan_sha256(review_plan)
    with connect(db_path) as connection:
        decision = connection.execute(
            """
            SELECT user_decision, module_02_permitted
            FROM decisions
            WHERE topic_run_id = ?
            ORDER BY decided_at DESC, rowid DESC
            LIMIT 1
            """,
            (topic_run_id,),
        ).fetchone()
        if decision is None:
            raise PermissionError("Module 02 requires an explicit Module 01 decision")
        if decision["user_decision"] != "approved" or not decision["module_02_permitted"]:
            raise PermissionError("Module 01 ended; Module 02 is not permitted")
        existing = connection.execute(
            "SELECT id FROM module02_runs WHERE topic_run_id = ?",
            (topic_run_id,),
        ).fetchone()
        if existing:
            connection.execute(
                """
                UPDATE module02_runs
                SET nature_index_snapshot_id = COALESCE(?, nature_index_snapshot_id),
                    review_query_plan_json = COALESCE(review_query_plan_json, ?),
                    review_query_plan_sha256 = COALESCE(review_query_plan_sha256, ?)
                WHERE id = ?
                """,
                (nature_snapshot_id, review_plan_json, review_plan_hash, existing["id"]),
            )
            return str(existing["id"])
        module02_run_id = new_id("module02")
        now = utc_now()
        connection.execute(
            """
            INSERT INTO module02_runs(
                id, topic_run_id, status, nature_index_snapshot_id,
                review_query_plan_json, review_query_plan_sha256, created_at, updated_at
            ) VALUES (?, ?, 'review_discovery', ?, ?, ?, ?, ?)
            """,
            (
                module02_run_id,
                topic_run_id,
                nature_snapshot_id,
                review_plan_json,
                review_plan_hash,
                now,
                now,
            ),
        )
    return module02_run_id


def get_module02_run(db_path: Path, module02_run_id: str) -> dict[str, Any]:
    init_module02_schema(db_path)
    with connect(db_path) as connection:
        row = connection.execute("SELECT * FROM module02_runs WHERE id = ?", (module02_run_id,)).fetchone()
    if row is None:
        raise KeyError(f"Unknown Module 02 run: {module02_run_id}")
    result = dict(row)
    result["perspectives"] = json.loads(result.pop("perspectives_json") or "[]")
    result["review_query_plan"] = json.loads(result.pop("review_query_plan_json") or "[]")
    return result


def frozen_review_query_for_run(
    db_path: Path, module02_run_id: str, query_id: str
) -> dict[str, Any]:
    run = get_module02_run(db_path, module02_run_id)
    for item in run.get("review_query_plan", []):
        if item["id"] == query_id:
            return item
    raise KeyError(f"Unknown frozen Module 02 review query id: {query_id}")


def start_module02_search(
    db_path: Path,
    *,
    module02_run_id: str,
    phase: str,
    query_id: str,
    scope: str,
    query: str,
    from_date: str | None,
    to_date: str | None,
    work_type_filter: str,
    raw_directory: Path,
) -> str:
    get_module02_run(db_path, module02_run_id)
    if phase == "reviews":
        limit = REVIEW_QUERY_LIMIT
        if scope != "review":
            raise ValueError("Review discovery requires scope=review")
    elif phase == "research":
        if scope not in RESEARCH_QUERY_LIMITS:
            raise ValueError(f"Research scope must be one of {sorted(RESEARCH_QUERY_LIMITS)}")
        limit = RESEARCH_QUERY_LIMITS[scope]
    else:
        raise ValueError("phase must be reviews or research")

    search_id = new_id("m02search")
    with connect(db_path) as connection:
        count = connection.execute(
            """
            SELECT COUNT(*) FROM module02_searches
            WHERE module02_run_id = ? AND phase = ? AND scope = ?
            """,
            (module02_run_id, phase, scope),
        ).fetchone()[0]
        duplicate = connection.execute(
            """
            SELECT 1 FROM module02_searches
            WHERE module02_run_id = ? AND phase = ? AND query_id = ?
            LIMIT 1
            """,
            (module02_run_id, phase, query_id),
        ).fetchone()
        if count >= limit:
            raise ValueError(f"Module 02 allows at most {limit} {scope} searches in phase {phase}")
        if duplicate:
            raise ValueError("This frozen Module 02 query id has already been attempted")
        connection.execute(
            """
            INSERT INTO module02_searches(
                id, module02_run_id, phase, query_id, scope, query, from_date, to_date,
                work_type_filter, raw_directory, status, started_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'running', ?)
            """,
            (
                search_id,
                module02_run_id,
                phase,
                query_id,
                scope,
                query,
                from_date,
                to_date,
                work_type_filter,
                str(raw_directory),
                utc_now(),
            ),
        )
    return search_id


def set_module02_search_raw_directory(db_path: Path, search_id: str, raw_directory: Path) -> None:
    with connect(db_path) as connection:
        connection.execute(
            "UPDATE module02_searches SET raw_directory = ? WHERE id = ?",
            (str(raw_directory), search_id),
        )


def finish_module02_search(
    db_path: Path,
    search_id: str,
    *,
    records_received: int,
    records_retained: int,
    provider_total: int | None = None,
    truncated: bool = False,
    error: str | None = None,
) -> None:
    with connect(db_path) as connection:
        connection.execute(
            """
            UPDATE module02_searches
            SET status = ?, records_received = ?, records_retained = ?,
                provider_total = ?, truncated = ?, error = ?, completed_at = ?
            WHERE id = ?
            """,
            (
                "failed" if error else "completed",
                records_received,
                records_retained,
                provider_total,
                int(truncated),
                error,
                utc_now(),
                search_id,
            ),
        )


def upsert_review(db_path: Path, module02_run_id: str, review: dict[str, Any]) -> tuple[str, bool]:
    with connect(db_path) as connection:
        row = None
        if review.get("openalex_id"):
            row = connection.execute(
                "SELECT id FROM module02_reviews WHERE module02_run_id = ? AND openalex_id = ?",
                (module02_run_id, review["openalex_id"]),
            ).fetchone()
        if row is None and review.get("doi"):
            row = connection.execute(
                "SELECT id FROM module02_reviews WHERE module02_run_id = ? AND doi = ?",
                (module02_run_id, review["doi"]),
            ).fetchone()
        if row is None:
            row = connection.execute(
                """
                SELECT id FROM module02_reviews
                WHERE module02_run_id = ? AND normalized_title = ? AND publication_year = ?
                LIMIT 1
                """,
                (module02_run_id, review["normalized_title"], review["publication_year"]),
            ).fetchone()
        if row:
            review_id = str(row["id"])
            connection.execute(
                """
                UPDATE module02_reviews
                SET cited_by_count = ?, citation_as_of = ?, paper_url = ?
                WHERE id = ?
                """,
                (review.get("cited_by_count"), review["citation_as_of"], review["paper_url"], review_id),
            )
            return review_id, False

        review_id = new_id("review")
        connection.execute(
            """
            INSERT INTO module02_reviews(
                id, module02_run_id, openalex_id, doi, title, normalized_title,
                abstract, publication_date, publication_year, journal, issn_l,
                cited_by_count, citation_as_of, paper_url, provider_work_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                review_id,
                module02_run_id,
                review.get("openalex_id"),
                review.get("doi"),
                review["title"],
                review["normalized_title"],
                review.get("abstract"),
                review.get("publication_date"),
                review["publication_year"],
                review.get("journal"),
                review.get("issn_l"),
                review.get("cited_by_count"),
                review["citation_as_of"],
                review["paper_url"],
                review.get("provider_work_type"),
            ),
        )
    return review_id, True


def save_review_screening(db_path: Path, module02_run_id: str, records: list[dict[str, Any]]) -> int:
    """Persist one complete screening pass and select exact or top-five adjacent reviews."""
    valid_confidence = {"low", "medium", "high"}
    valid_match_levels = {"exact", "adjacent", "excluded"}
    supplied_ids = {record["review_id"] for record in records}
    if len(supplied_ids) != len(records):
        raise ValueError("Review screening contains duplicate review ids")

    with connect(db_path) as connection:
        expected_ids = {
            str(row["id"])
            for row in connection.execute(
                "SELECT id FROM module02_reviews WHERE module02_run_id = ?",
                (module02_run_id,),
            ).fetchall()
        }
        if supplied_ids != expected_ids:
            missing = len(expected_ids - supplied_ids)
            unknown = len(supplied_ids - expected_ids)
            raise ValueError(
                f"Review screening must cover every candidate once (missing={missing}, unknown={unknown})"
            )

        now = utc_now()
        for record in records:
            if record["confidence"] not in valid_confidence:
                raise ValueError(f"Invalid review-screening confidence: {record['confidence']}")
            match_level = record["match_level"]
            if match_level not in valid_match_levels:
                raise ValueError(f"Invalid review match level: {match_level}")
            score = float(record["relevance_score"])
            if not 0.0 <= score <= 1.0:
                raise ValueError("Review relevance_score must be between 0 and 1")
            keywords = record.get("matched_keywords", [])
            if match_level == "adjacent" and not keywords:
                raise ValueError("Adjacent reviews require at least one matched important keyword")
            connection.execute(
                """
                UPDATE module02_reviews
                SET relevance_status = 'screened', review_match_level = ?,
                    review_relevance_score = ?, matched_keywords_json = ?,
                    screening_confidence = ?, screening_reason = ?, screened_at = ?
                WHERE id = ? AND module02_run_id = ?
                """,
                (
                    match_level,
                    score,
                    json.dumps(keywords, ensure_ascii=False),
                    record["confidence"],
                    record["reason"],
                    now,
                    record["review_id"],
                    module02_run_id,
                ),
            )

        exact_count = connection.execute(
            """
            SELECT COUNT(*) FROM module02_reviews
            WHERE module02_run_id = ? AND review_match_level = 'exact'
            """,
            (module02_run_id,),
        ).fetchone()[0]
        connection.execute(
            "UPDATE module02_reviews SET relevance_status = 'excluded' WHERE module02_run_id = ?",
            (module02_run_id,),
        )
        if exact_count:
            connection.execute(
                """
                UPDATE module02_reviews SET relevance_status = 'included'
                WHERE module02_run_id = ? AND review_match_level = 'exact'
                """,
                (module02_run_id,),
            )
        else:
            adjacent_rows = connection.execute(
                """
                SELECT id FROM module02_reviews
                WHERE module02_run_id = ? AND review_match_level = 'adjacent'
                ORDER BY review_relevance_score DESC, cited_by_count DESC,
                         publication_date DESC, id
                LIMIT 5
                """,
                (module02_run_id,),
            ).fetchall()
            if adjacent_rows:
                placeholders = ",".join("?" for _ in adjacent_rows)
                connection.execute(
                    f"UPDATE module02_reviews SET relevance_status = 'included' WHERE id IN ({placeholders})",
                    tuple(row["id"] for row in adjacent_rows),
                )
    return len(records)


def save_fulltext_access(db_path: Path, module02_run_id: str, records: list[dict[str, Any]]) -> int:
    downloaded_statuses = {"oa_downloaded", "institutional_downloaded"}
    valid_statuses = downloaded_statuses | {
        "login_required",
        "institution_not_subscribed",
        "license_restricted",
        "download_failed",
        "skipped",
    }
    updated = 0
    invalidate_downstream = False
    with connect(db_path) as connection:
        for record in records:
            status = record["status"]
            if status not in valid_statuses:
                raise ValueError(f"Invalid full-text access status: {status}")
            review = connection.execute(
                """
                SELECT relevance_status, fulltext_access_status, analyzed_at
                FROM module02_reviews WHERE id = ? AND module02_run_id = ?
                """,
                (record["review_id"], module02_run_id),
            ).fetchone()
            if review is None:
                raise KeyError(f"Unknown review for this Module 02 run: {record['review_id']}")
            if status in downloaded_statuses and review["relevance_status"] != "included":
                raise ValueError("Only semantically included reviews may enter PDF download")

            pdf_path: str | None = None
            pdf_sha256: str | None = None
            if status in downloaded_statuses:
                supplied_path = record.get("pdf_path")
                if not supplied_path:
                    raise ValueError(f"{status} requires pdf_path")
                path = Path(supplied_path)
                if not path.is_absolute():
                    raise ValueError("Downloaded PDF path must be absolute")
                if not path.is_file():
                    raise ValueError(f"Downloaded PDF does not exist: {path}")
                if path.stat().st_size > 100 * 1024 * 1024:
                    raise ValueError("Downloaded PDF exceeds the 100 MiB safety limit")
                with path.open("rb") as stream:
                    if stream.read(5) != b"%PDF-":
                        raise ValueError("Downloaded file does not have a PDF signature")
                    stream.seek(0)
                    digest = hashlib.sha256()
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(chunk)
                pdf_path = str(path)
                pdf_sha256 = digest.hexdigest()
            elif record.get("pdf_path") is not None:
                raise ValueError(f"{status} must not include pdf_path")

            connection.execute(
                """
                UPDATE module02_reviews
                SET fulltext_access_status = ?, fulltext_source_url = ?, pdf_path = ?,
                    pdf_sha256 = ?, fulltext_license = ?, fulltext_note = ?,
                    fulltext_checked_at = ?
                WHERE id = ?
                """,
                (
                    status,
                    record.get("source_url"),
                    pdf_path,
                    pdf_sha256,
                    record.get("license"),
                    record.get("note"),
                    utc_now(),
                    record["review_id"],
                ),
            )
            if (
                status in downloaded_statuses
                and review["fulltext_access_status"] not in downloaded_statuses
                and review["analyzed_at"] is not None
            ):
                connection.execute(
                    """
                    UPDATE module02_reviews
                    SET evidence_level = NULL, review_reason = NULL, structure_json = NULL,
                        future_trends_json = NULL, source_urls_json = NULL,
                        limitations_json = NULL, analyzed_at = NULL
                    WHERE id = ?
                    """,
                    (record["review_id"],),
                )
                invalidate_downstream = True
            updated += 1
        if invalidate_downstream:
            connection.execute(
                "DELETE FROM module02_trend_claims WHERE module02_run_id = ?",
                (module02_run_id,),
            )
            connection.execute(
                """
                UPDATE module02_research
                SET category = 'pending', matched_review_ids_json = '[]',
                    matched_trend_claim_ids_json = '[]', matched_future_trends_json = '[]',
                    rationale = NULL, confidence = NULL, classified_at = NULL
                WHERE module02_run_id = ?
                """,
                (module02_run_id,),
            )
            connection.execute(
                """
                UPDATE module02_runs
                SET status = 'review_analysis', trend_claims_finalized = 0,
                    research_comparison_finalized = 0, newest_review_id = NULL,
                    newest_review_date = NULL, trend_baseline_review_id = NULL,
                    trend_baseline_review_date = NULL, research_from_date = NULL,
                    research_to_date = NULL, perspectives_json = NULL, updated_at = ?
                WHERE id = ?
                """,
                (utc_now(), module02_run_id),
            )
    return updated


def _upsert_shared_paper(connection: Any, paper: dict[str, Any]) -> tuple[str, bool]:
    row = None
    if paper.get("openalex_id"):
        row = connection.execute("SELECT id FROM papers WHERE openalex_id = ?", (paper["openalex_id"],)).fetchone()
    if row is None and paper.get("doi"):
        row = connection.execute("SELECT id FROM papers WHERE doi = ?", (paper["doi"],)).fetchone()
    if row is None:
        row = connection.execute(
            "SELECT id FROM papers WHERE normalized_title = ? AND publication_year = ? LIMIT 1",
            (paper["normalized_title"], paper["publication_year"]),
        ).fetchone()
    if row:
        return str(row["id"]), False

    paper_id = paper["paper_id"]
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
    return paper_id, True


def upsert_module02_research(
    db_path: Path,
    module02_run_id: str,
    paper: dict[str, Any],
    *,
    origin: str,
    scope: str,
) -> tuple[str, bool]:
    with connect(db_path) as connection:
        paper_id, is_new = _upsert_shared_paper(connection, paper)
        connection.execute(
            """
            INSERT OR IGNORE INTO module02_research(module02_run_id, paper_id, origin, scope)
            VALUES (?, ?, ?, ?)
            """,
            (module02_run_id, paper_id, origin, scope),
        )
    return paper_id, is_new


def save_review_analyses(db_path: Path, module02_run_id: str, analyses: list[dict[str, Any]]) -> int:
    updated = 0
    with connect(db_path) as connection:
        for analysis in analyses:
            review_id = analysis["review_id"]
            review = connection.execute(
                """
                SELECT relevance_status, review_match_level, fulltext_access_status
                FROM module02_reviews
                WHERE id = ? AND module02_run_id = ?
                """,
                (review_id, module02_run_id),
            ).fetchone()
            if review is None:
                raise KeyError(f"Unknown review for this Module 02 run: {review_id}")
            if review["relevance_status"] != "included":
                raise ValueError(f"Review analysis is allowed only for selected reviews: {review_id}")
            if review["fulltext_access_status"] in {"login_required", "download_failed"}:
                raise ValueError(
                    f"Resolve institutional access choice before review analysis: {review_id}"
                )
            if analysis["review_match_level"] != review["review_match_level"]:
                raise ValueError(f"Review-analysis match level does not match screening: {review_id}")
            if analysis["fulltext_access_status"] != review["fulltext_access_status"]:
                raise ValueError(f"Full-text access status mismatch for review: {review_id}")
            if analysis["evidence_level"] == "full_text" and review["fulltext_access_status"] not in {
                "oa_downloaded", "institutional_downloaded"
            }:
                raise ValueError(f"Full-text analysis requires a registered PDF: {review_id}")
            connection.execute(
                """
                UPDATE module02_reviews
                SET nature_index_status = ?, evidence_level = ?, review_reason = ?,
                    structure_json = ?, future_trends_json = ?, source_urls_json = ?,
                    limitations_json = ?, analyzed_at = ?
                WHERE id = ?
                """,
                (
                    analysis["nature_index_status"],
                    analysis["evidence_level"],
                    analysis.get("review_reason"),
                    json.dumps(analysis.get("structure", []), ensure_ascii=False),
                    json.dumps(analysis.get("future_trends", []), ensure_ascii=False),
                    json.dumps(analysis.get("source_urls", []), ensure_ascii=False),
                    json.dumps(analysis.get("limitations", []), ensure_ascii=False),
                    utc_now(),
                    review_id,
                ),
            )
            updated += 1
        connection.execute(
            "UPDATE module02_runs SET status = 'review_analysis', updated_at = ? WHERE id = ?",
            (utc_now(), module02_run_id),
        )
    return updated


def subtract_calendar_months(value: date, months: int) -> date:
    absolute_month = value.year * 12 + value.month - 1 - months
    year, zero_based_month = divmod(absolute_month, 12)
    month = zero_based_month + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def finalize_review_anchor(db_path: Path, module02_run_id: str, as_of: date | None = None) -> dict[str, Any]:
    run = get_module02_run(db_path, module02_run_id)
    topic_run = get_topic_run(db_path, run["topic_run_id"])
    end = as_of or datetime.now(UTC).date()
    with connect(db_path) as connection:
        pending_count = connection.execute(
            "SELECT COUNT(*) FROM module02_reviews WHERE module02_run_id = ? AND relevance_status IN ('pending', 'screened')",
            (module02_run_id,),
        ).fetchone()[0]
        if pending_count:
            raise ValueError("Complete review relevance analysis before finalizing the anchor")
        incomplete_reviews = connection.execute(
            """
            SELECT COUNT(*) FROM module02_reviews
            WHERE module02_run_id = ? AND relevance_status = 'included'
              AND (fulltext_access_status IN ('not_checked', 'login_required', 'download_failed') OR analyzed_at IS NULL)
            """,
            (module02_run_id,),
        ).fetchone()[0]
        if incomplete_reviews:
            raise ValueError("Complete selected-review access and analysis before finalizing the anchor")
        trend_finalized = connection.execute(
            "SELECT trend_claims_finalized FROM module02_runs WHERE id = ?",
            (module02_run_id,),
        ).fetchone()[0]
        if not trend_finalized:
            raise ValueError("Finalize TrendClaims, including an explicit empty set, before the anchor")

        review = connection.execute(
            """
            SELECT id, title, publication_date, review_match_level
            FROM module02_reviews
            WHERE module02_run_id = ? AND relevance_status = 'included' AND publication_date IS NOT NULL
            ORDER BY publication_date DESC, id
            LIMIT 1
            """,
            (module02_run_id,),
        ).fetchone()
        baseline = connection.execute(
            """
            SELECT id, title, publication_date
            FROM module02_reviews
            WHERE module02_run_id = ?
              AND relevance_status = 'included'
              AND evidence_level = 'full_text'
              AND fulltext_access_status IN ('oa_downloaded', 'institutional_downloaded')
              AND future_trends_json IS NOT NULL
              AND future_trends_json != '[]'
            ORDER BY publication_date DESC, id
            LIMIT 1
            """,
            (module02_run_id,),
        ).fetchone()

        if review is None:
            profile_window = topic_run["profile"].get("time_windows", {})
            fallback_from, _ = rolling_two_year_window(end)
            start_value = profile_window.get("publication_from", fallback_from)
            start = date.fromisoformat(start_value)
            if start > end:
                start = date.fromisoformat(fallback_from)
            branch = "no_related_reviews"
            status = "research_collection_no_review"
            review_date = None
        else:
            review_date = date.fromisoformat(review["publication_date"])
            if review_date > end:
                raise ValueError("Newest review publication date is after the current system date")
            start = subtract_calendar_months(review_date, 6)
            branch = (
                "adjacent_review_fallback"
                if review["review_match_level"] == "adjacent"
                else "exact_review_anchored"
            )
            status = "research_collection"

        connection.execute(
            """
            UPDATE module02_runs
            SET newest_review_id = ?, newest_review_date = ?,
                trend_baseline_review_id = ?, trend_baseline_review_date = ?,
                research_from_date = ?, research_to_date = ?, status = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                review["id"] if review else None,
                review_date.isoformat() if review_date else None,
                baseline["id"] if baseline else None,
                baseline["publication_date"] if baseline else None,
                start.isoformat(),
                end.isoformat(),
                status,
                utc_now(),
                module02_run_id,
            ),
        )
        placeholders = ",".join("?" for _ in RESEARCH_WORK_TYPES)
        connection.execute(
            f"""
            INSERT OR IGNORE INTO module02_research(module02_run_id, paper_id, origin, scope)
            SELECT ?, p.id, 'module01', rp.retrieval_scope
            FROM run_papers rp
            JOIN papers p ON p.id = rp.paper_id
            WHERE rp.topic_run_id = ?
              AND p.publication_date BETWEEN ? AND ?
              AND p.work_type IN ({placeholders})
              AND rp.retrieval_scope IN ('direct', 'technical')
              AND rp.relevance_label IN ('direct', 'technical')
            """,
            (module02_run_id, run["topic_run_id"], start.isoformat(), end.isoformat(), *RESEARCH_WORK_TYPES),
        )
    return {
        "module02_run_id": module02_run_id,
        "branch": branch,
        "newest_review_id": review["id"] if review else None,
        "newest_review_title": review["title"] if review else None,
        "newest_review_date": review_date.isoformat() if review_date else None,
        "trend_baseline_review_id": baseline["id"] if baseline else None,
        "trend_baseline_review_title": baseline["title"] if baseline else None,
        "trend_baseline_review_date": baseline["publication_date"] if baseline else None,
        "research_from_date": start.isoformat(),
        "research_to_date": end.isoformat(),
    }


def plan_module02_research_queries(db_path: Path, module02_run_id: str) -> list[dict[str, Any]]:
    run = get_module02_run(db_path, module02_run_id)
    if not run.get("research_from_date") or not run.get("research_to_date"):
        raise ValueError("Finalize the review anchor before planning research queries")
    topic_run = get_topic_run(db_path, run["topic_run_id"])
    profile_queries = [
        query for query in topic_run["profile"].get("queries", [])
        if query.get("scope") in {"direct", "technical"}
    ]
    plans: list[dict[str, Any]] = []
    with connect(db_path) as connection:
        for query in profile_queries:
            module01_rows = connection.execute(
                """
                SELECT status, from_date, to_date, records_received
                FROM search_runs
                WHERE topic_run_id = ?
                  AND (query_id = ? OR (query_id IS NULL AND scope = ? AND query = ?))
                ORDER BY started_at DESC
                """,
                (run["topic_run_id"], query["id"], query["scope"], query["query"]),
            ).fetchall()
            module02_row = connection.execute(
                """
                SELECT status, truncated FROM module02_searches
                WHERE module02_run_id = ? AND phase = 'research'
                  AND (query_id = ? OR (query_id IS NULL AND scope = ? AND query = ?))
                ORDER BY started_at DESC LIMIT 1
                """,
                (module02_run_id, query["id"], query["scope"], query["query"]),
            ).fetchone()
            covered = any(
                row["status"] == "completed"
                and row["from_date"] <= run["research_from_date"]
                and row["to_date"] >= run["research_to_date"]
                and row["records_received"] < 50
                for row in module01_rows
            )
            if module02_row and module02_row["status"] == "completed" and not module02_row["truncated"]:
                action = "already_supplemented"
                reason = "A complete Module 02 search already covers this query."
            elif covered:
                action = "reuse_module01"
                reason = "Module 01 completed this query over the full anchor window without hitting its page cap."
            else:
                action = "supplement"
                reason = "Module 01 did not complete this exact query/window or reached its 50-record page cap."
            plans.append({
                "id": query.get("id"),
                "scope": query["scope"],
                "query": query["query"],
                "action": action,
                "reason": reason,
            })
    return plans


def export_reviews(db_path: Path, module02_run_id: str, *, included_only: bool = False) -> list[dict[str, Any]]:
    get_module02_run(db_path, module02_run_id)
    with connect(db_path) as connection:
        where = " AND relevance_status = 'included'" if included_only else ""
        rows = connection.execute(
            f"SELECT * FROM module02_reviews WHERE module02_run_id = ?{where} ORDER BY publication_date DESC, title",
            (module02_run_id,),
        ).fetchall()
    results = []
    for row in rows:
        item = dict(row)
        for field in (
            "matched_keywords_json",
            "structure_json",
            "future_trends_json",
            "source_urls_json",
            "limitations_json",
        ):
            item[field.removesuffix("_json")] = json.loads(item.pop(field) or "[]")
        results.append(item)
    return results


def save_trend_claims(db_path: Path, module02_run_id: str, claims: list[dict[str, Any]]) -> int:
    get_module02_run(db_path, module02_run_id)
    seen: set[str] = set()
    with connect(db_path) as connection:
        connection.execute("DELETE FROM module02_trend_claims WHERE module02_run_id = ?", (module02_run_id,))
        for claim in claims:
            trend_id = claim["trend_id"]
            if trend_id in seen:
                raise ValueError(f"Duplicate trend_id: {trend_id}")
            seen.add(trend_id)
            for review_id in claim["source_review_ids"]:
                source = connection.execute(
                    """
                    SELECT relevance_status, evidence_level, fulltext_access_status
                    FROM module02_reviews WHERE module02_run_id = ? AND id = ?
                    """,
                    (module02_run_id, review_id),
                ).fetchone()
                if source is None:
                    raise KeyError(f"Unknown source review for trend claim: {review_id}")
                if source["relevance_status"] != "included" or source["evidence_level"] != "full_text":
                    raise ValueError(f"Trend claim requires an included full-text review: {review_id}")
                if source["fulltext_access_status"] not in {"oa_downloaded", "institutional_downloaded"}:
                    raise ValueError(f"Trend claim source has no registered PDF: {review_id}")
            connection.execute(
                """
                INSERT INTO module02_trend_claims(
                    id, module02_run_id, canonical_label, description,
                    source_review_ids_json, source_statements_json, scope_note, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trend_id,
                    module02_run_id,
                    claim["canonical_label"],
                    claim["description"],
                    json.dumps(claim["source_review_ids"], ensure_ascii=False),
                    json.dumps(claim["source_statements"], ensure_ascii=False),
                    claim.get("scope_note"),
                    utc_now(),
                ),
            )
        connection.execute(
            """
            UPDATE module02_runs
            SET trend_claims_finalized = 1, status = 'trend_claims_ready', updated_at = ?
            WHERE id = ?
            """,
            (utc_now(), module02_run_id),
        )
    return len(claims)


def export_trend_claims(db_path: Path, module02_run_id: str) -> list[dict[str, Any]]:
    get_module02_run(db_path, module02_run_id)
    with connect(db_path) as connection:
        rows = connection.execute(
            "SELECT * FROM module02_trend_claims WHERE module02_run_id = ? ORDER BY canonical_label, id",
            (module02_run_id,),
        ).fetchall()
    results = []
    for row in rows:
        item = dict(row)
        item["source_review_ids"] = json.loads(item.pop("source_review_ids_json"))
        item["source_statements"] = json.loads(item.pop("source_statements_json"))
        results.append(item)
    return results


def export_research(db_path: Path, module02_run_id: str) -> list[dict[str, Any]]:
    get_module02_run(db_path, module02_run_id)
    with connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT p.*, mr.origin, mr.scope, mr.category,
                   mr.matched_review_ids_json, mr.matched_trend_claim_ids_json,
                   mr.matched_future_trends_json, mr.rationale, mr.confidence, mr.classified_at
            FROM module02_research mr
            JOIN papers p ON p.id = mr.paper_id
            WHERE mr.module02_run_id = ?
            ORDER BY p.publication_date DESC, p.title
            """,
            (module02_run_id,),
        ).fetchall()
    results = []
    for row in rows:
        item = dict(row)
        item["matched_review_ids"] = json.loads(item.pop("matched_review_ids_json") or "[]")
        item["matched_trend_claim_ids"] = json.loads(item.pop("matched_trend_claim_ids_json") or "[]")
        item["matched_future_trends"] = json.loads(item.pop("matched_future_trends_json") or "[]")
        results.append(item)
    return results


def save_research_comparisons(db_path: Path, module02_run_id: str, papers: list[dict[str, Any]]) -> int:
    valid_categories = {"trend_consistent", "trend_extension", "new_direction", "excluded"}
    updated = 0
    with connect(db_path) as connection:
        available_trends = {
            row["id"] for row in connection.execute(
                "SELECT id FROM module02_trend_claims WHERE module02_run_id = ?",
                (module02_run_id,),
            )
        }
        for paper in papers:
            category = paper["category"]
            if category not in valid_categories:
                raise ValueError(f"Invalid comparison category: {category}")
            trend_ids = paper.get("matched_trend_claim_ids", [])
            unknown_trends = set(trend_ids) - available_trends
            if unknown_trends:
                raise KeyError(f"Unknown trend claims: {sorted(unknown_trends)}")
            if category in {"trend_consistent", "trend_extension"} and not trend_ids:
                raise ValueError(f"{category} requires at least one matched TrendClaim")
            if category == "new_direction" and trend_ids:
                raise ValueError("new_direction must not claim a matched TrendClaim")
            cursor = connection.execute(
                """
                UPDATE module02_research
                SET category = ?, matched_review_ids_json = ?, matched_trend_claim_ids_json = ?,
                    matched_future_trends_json = ?, rationale = ?, confidence = ?, classified_at = ?
                WHERE module02_run_id = ? AND paper_id = ?
                """,
                (
                    category,
                    json.dumps(paper.get("matched_review_ids", []), ensure_ascii=False),
                    json.dumps(trend_ids, ensure_ascii=False),
                    json.dumps(paper.get("matched_future_trends", []), ensure_ascii=False),
                    paper["rationale"],
                    paper["confidence"],
                    utc_now(),
                    module02_run_id,
                    paper["paper_id"],
                ),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"Unknown research paper for this Module 02 run: {paper['paper_id']}")
            updated += 1
        connection.execute(
            "UPDATE module02_runs SET status = 'research_analysis_in_progress', updated_at = ? WHERE id = ?",
            (utc_now(), module02_run_id),
        )
    return updated


def save_perspectives(db_path: Path, module02_run_id: str, perspectives: list[dict[str, Any]]) -> None:
    if not 3 <= len(perspectives) <= 5:
        raise ValueError("Module 02 requires between 3 and 5 review perspectives")
    ranks = [item["rank"] for item in perspectives]
    if len(set(ranks)) != len(ranks) or any(rank < 1 or rank > 5 for rank in ranks):
        raise ValueError("Perspective ranks must be unique integers from 1 to 5")
    run = get_module02_run(db_path, module02_run_id)
    if not run.get("research_comparison_finalized"):
        raise ValueError("Finalize Module 02 research comparison before saving perspectives")
    now = utc_now()
    with connect(db_path) as connection:
        for perspective in perspectives:
            connection.execute(
                """
                INSERT INTO module03_perspective_branches(
                    id, module02_run_id, perspective_rank, perspective_title,
                    perspective_json, status, created_at
                ) VALUES (?, ?, ?, ?, ?, 'available', ?)
                ON CONFLICT(module02_run_id, perspective_rank)
                DO UPDATE SET
                    perspective_title = excluded.perspective_title,
                    perspective_json = excluded.perspective_json
                """,
                (
                    new_id("perspective"),
                    module02_run_id,
                    perspective["rank"],
                    perspective["candidate_title"],
                    json.dumps(perspective, ensure_ascii=False),
                    now,
                ),
            )
        connection.execute(
            """
            UPDATE module02_runs
            SET perspectives_json = ?, status = 'perspectives_ready', updated_at = ?
            WHERE id = ?
            """,
            (json.dumps(perspectives, ensure_ascii=False), now, module02_run_id),
        )


def list_perspective_branches(db_path: Path, module02_run_id: str) -> list[dict[str, Any]]:
    get_module02_run(db_path, module02_run_id)
    with connect(db_path) as connection:
        has_outline_table = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'module03_outline_runs'"
        ).fetchone() is not None
        if has_outline_table:
            rows = connection.execute(
                """
                SELECT b.*, r.id AS module03_run_id, r.status AS module03_outline_status,
                       r.current_version AS module03_outline_version
                FROM module03_perspective_branches b
                LEFT JOIN module03_outline_runs r ON r.perspective_branch_id = b.id
                WHERE b.module02_run_id = ? ORDER BY b.perspective_rank
                """,
                (module02_run_id,),
            ).fetchall()
        else:
            rows = connection.execute(
                """
                SELECT *, NULL AS module03_run_id, NULL AS module03_outline_status,
                       NULL AS module03_outline_version
                FROM module03_perspective_branches
                WHERE module02_run_id = ? ORDER BY perspective_rank
                """,
                (module02_run_id,),
            ).fetchall()
    results = []
    for row in rows:
        item = dict(row)
        item["perspective"] = json.loads(item.pop("perspective_json"))
        results.append(item)
    return results


def attach_perspective_sessions(
    db_path: Path,
    module02_run_id: str,
    branches: list[dict[str, Any]],
) -> int:
    seen_ranks: set[int] = set()
    seen_sessions: set[str] = set()
    updated = 0
    with connect(db_path) as connection:
        for branch in branches:
            rank = branch["rank"]
            session_id = branch["session_id"]
            if rank in seen_ranks or session_id in seen_sessions:
                raise ValueError("Perspective branch ranks and session ids must be unique")
            seen_ranks.add(rank)
            seen_sessions.add(session_id)
            cursor = connection.execute(
                """
                UPDATE module03_perspective_branches
                SET dsh_session_id = ?
                WHERE module02_run_id = ? AND perspective_rank = ?
                """,
                (session_id, module02_run_id, rank),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"Unknown perspective rank for this Module 02 run: {rank}")
            updated += 1
    return updated


def rebuild_perspective_selection(db_path: Path, module02_run_id: str) -> dict[str, Any]:
    branches = list_perspective_branches(db_path, module02_run_id)
    if not branches:
        raise ValueError("No saved perspectives are available for selection")
    return {
        "module02_run_id": module02_run_id,
        "question": "请选择一个综述写作视角。选择后将为该视角启动或恢复Module 03大纲设计。",
        "options": [
            {
                "rank": branch["perspective_rank"],
                "label": f"视角{branch['perspective_rank']}｜{branch['perspective_title']}",
                "branch_status": branch["status"],
                "session_id": branch.get("dsh_session_id"),
                "module03_run_id": branch.get("module03_run_id"),
                "outline_status": branch.get("module03_outline_status"),
                "outline_version": branch.get("module03_outline_version"),
            }
            for branch in branches
        ],
        "selected_rank": None,
        "module03_status": "outline_available",
        "message": "请选择视角以开始Module 03大纲设计",
    }


def select_perspective_branch(db_path: Path, module02_run_id: str, rank: int) -> dict[str, Any]:
    with connect(db_path) as connection:
        row = connection.execute(
            """
            SELECT * FROM module03_perspective_branches
            WHERE module02_run_id = ? AND perspective_rank = ?
            """,
            (module02_run_id, rank),
        ).fetchone()
        if row is None:
            raise KeyError(f"Unknown perspective rank for this Module 02 run: {rank}")
        selected_at = utc_now()
        connection.execute(
            """
            UPDATE module03_perspective_branches
            SET status = 'selected_for_module03', selected_at = ?
            WHERE id = ?
            """,
            (selected_at, row["id"]),
        )
    result = dict(row)
    result["status"] = "selected_for_module03"
    result["selected_at"] = selected_at
    result["perspective"] = json.loads(result.pop("perspective_json"))
    result["selected_rank"] = rank
    result["module03_status"] = "outline_ready"
    result["message"] = "Module 03大纲设计已授权"
    return result


def finalize_research_comparison(db_path: Path, module02_run_id: str) -> dict[str, Any]:
    """Close research comparison only after retrieval and every paper classification."""
    get_module02_run(db_path, module02_run_id)
    outstanding = [
        item["id"] for item in plan_module02_research_queries(db_path, module02_run_id)
        if item["action"] == "supplement"
    ]
    if outstanding:
        raise ValueError(f"Cannot finalize research comparison before frozen supplements: {outstanding}")
    with connect(db_path) as connection:
        pending = connection.execute(
            """
            SELECT COUNT(*) FROM module02_research
            WHERE module02_run_id = ? AND category = 'pending'
            """,
            (module02_run_id,),
        ).fetchone()[0]
        if pending:
            raise ValueError(f"Cannot finalize research comparison: {pending} papers remain pending")
        count = connection.execute(
            "SELECT COUNT(*) FROM module02_research WHERE module02_run_id = ?",
            (module02_run_id,),
        ).fetchone()[0]
        connection.execute(
            """
            UPDATE module02_runs
            SET research_comparison_finalized = 1,
                status = 'research_analysis', updated_at = ?
            WHERE id = ?
            """,
            (utc_now(), module02_run_id),
        )
    return {
        "module02_run_id": module02_run_id,
        "classified_papers": count,
        "status": "research_analysis",
    }


def module02_next_action(db_path: Path, module02_run_id: str) -> dict[str, Any]:
    """Return the next deterministic Module 02 step for every supported runtime."""
    run = get_module02_run(db_path, module02_run_id)
    with connect(db_path) as connection:
        unresolved_access = connection.execute(
            """
            SELECT COUNT(*) FROM module02_reviews
            WHERE module02_run_id = ? AND relevance_status = 'included'
              AND fulltext_access_status IN ('login_required', 'download_failed')
            """,
            (module02_run_id,),
        ).fetchone()[0]
    if (
        run.get("status") == "perspectives_ready"
        and len(run.get("perspectives", [])) >= 3
        and not unresolved_access
    ):
        return {
            "module02_run_id": module02_run_id,
            "action": "render_outputs_and_select_perspective",
            "blocking_user_input": True,
            "status": "perspectives_ready",
        }
    with connect(db_path) as connection:
        searches = connection.execute(
            """
            SELECT query_id, query, work_type_filter, status
            FROM module02_searches
            WHERE module02_run_id = ? AND phase = 'reviews'
            """,
            (module02_run_id,),
        ).fetchall()
        attempted_review_ids = {row["query_id"] for row in searches if row["query_id"]}
        attempted_review_queries = {
            (row["query"], row["work_type_filter"] == "review") for row in searches
        }
        missing_review_queries = [
            item for item in run.get("review_query_plan", [])
            if item["id"] not in attempted_review_ids
            and (item["query"], bool(item["typed_only"])) not in attempted_review_queries
        ]
        legacy_complete = (
            searches
            and all(row["query_id"] is None for row in searches)
            and len(searches) >= len(run.get("review_query_plan", []))
        )
        if legacy_complete:
            missing_review_queries = []
        if missing_review_queries:
            return {
                "module02_run_id": module02_run_id,
                "action": "search_reviews",
                "blocking_user_input": False,
                "queries": missing_review_queries,
            }

        pending_reviews = connection.execute(
            """
            SELECT COUNT(*) FROM module02_reviews
            WHERE module02_run_id = ? AND relevance_status IN ('pending', 'screened')
            """,
            (module02_run_id,),
        ).fetchone()[0]
        if pending_reviews:
            return {
                "module02_run_id": module02_run_id,
                "action": "screen_reviews",
                "blocking_user_input": False,
                "candidate_count": pending_reviews,
            }

        unchecked = connection.execute(
            """
            SELECT id, title FROM module02_reviews
            WHERE module02_run_id = ? AND relevance_status = 'included'
              AND fulltext_access_status = 'not_checked'
            ORDER BY publication_date DESC, id
            """,
            (module02_run_id,),
        ).fetchall()
        if unchecked:
            return {
                "module02_run_id": module02_run_id,
                "action": "check_fulltext",
                "blocking_user_input": False,
                "reviews": [dict(row) for row in unchecked],
                "fallback": "Check legal open access first. If none exists, persist login_required and call module02-next; do not silently skip institutional access.",
            }

        access_required = connection.execute(
            """
            SELECT id, title, paper_url FROM module02_reviews
            WHERE module02_run_id = ? AND relevance_status = 'included'
              AND fulltext_access_status IN ('login_required', 'download_failed')
            ORDER BY publication_date DESC, id
            """,
            (module02_run_id,),
        ).fetchall()
        if access_required:
            return {
                "module02_run_id": module02_run_id,
                "action": "request_institutional_access",
                "blocking_user_input": True,
                "reviews": [
                    {
                        **dict(row),
                        "suggested_pdf_path": f"runtime/institutional-pdfs/{row['id']}.pdf",
                    }
                    for row in access_required
                ],
                "prompt": [
                    "1. 我将在学校官方页面登录并下载PDF",
                    "2. 学校没有订阅，跳过全文",
                    "3. 不使用学校权限，按摘要继续",
                ],
                "security": "Never enter institution credentials, MFA codes, or cookies in chat.",
            }

        unanalyzed = connection.execute(
            """
            SELECT id, title FROM module02_reviews
            WHERE module02_run_id = ? AND relevance_status = 'included'
              AND analyzed_at IS NULL
            ORDER BY publication_date DESC, id
            """,
            (module02_run_id,),
        ).fetchall()
        if unanalyzed:
            return {
                "module02_run_id": module02_run_id,
                "action": "analyze_reviews",
                "blocking_user_input": False,
                "reviews": [dict(row) for row in unanalyzed],
            }

    if not run.get("trend_claims_finalized"):
        return {
            "module02_run_id": module02_run_id,
            "action": "normalize_trend_claims",
            "blocking_user_input": False,
            "note": "Persist an empty list when no full-text trend evidence exists.",
        }

    if not run.get("research_from_date") or not run.get("research_to_date"):
        return {
            "module02_run_id": module02_run_id,
            "action": "finalize_review_anchor",
            "blocking_user_input": False,
        }

    research_plan = plan_module02_research_queries(db_path, module02_run_id)
    supplement = [item for item in research_plan if item["action"] == "supplement"]
    if supplement:
        return {
            "module02_run_id": module02_run_id,
            "action": "search_research",
            "blocking_user_input": False,
            "queries": supplement,
        }

    with connect(db_path) as connection:
        pending_papers = connection.execute(
            """
            SELECT COUNT(*) FROM module02_research
            WHERE module02_run_id = ? AND category = 'pending'
            """,
            (module02_run_id,),
        ).fetchone()[0]
    if pending_papers:
        return {
            "module02_run_id": module02_run_id,
            "action": "compare_research",
            "blocking_user_input": False,
            "paper_count": pending_papers,
        }
    if not run.get("research_comparison_finalized"):
        return {
            "module02_run_id": module02_run_id,
            "action": "finalize_research_comparison",
            "blocking_user_input": False,
        }

    if len(run.get("perspectives", [])) < 3:
        return {
            "module02_run_id": module02_run_id,
            "action": "generate_perspectives",
            "blocking_user_input": False,
            "required_count": "3-5",
        }

    return {
        "module02_run_id": module02_run_id,
        "action": "render_outputs_and_select_perspective",
        "blocking_user_input": True,
        "status": "perspectives_ready",
    }
