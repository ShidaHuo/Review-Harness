from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from .models import new_id
from .storage import connect, get_topic_run, init_db

REFERENCE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS nature_index_snapshots (
    id TEXT PRIMARY KEY,
    source_url TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    edition TEXT,
    content_sha256 TEXT NOT NULL UNIQUE,
    stated_journal_count INTEGER NOT NULL,
    stated_other_venue_count INTEGER NOT NULL,
    publications_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS topic_run_references (
    topic_run_id TEXT NOT NULL REFERENCES topic_runs(id),
    reference_kind TEXT NOT NULL,
    snapshot_id TEXT NOT NULL REFERENCES nature_index_snapshots(id),
    PRIMARY KEY(topic_run_id, reference_kind)
);
"""

BUNDLED_NATURE_INDEX_PATH = (
    Path(__file__).resolve().parents[2]
    / ".dsh"
    / "skills"
    / "research-topic-evaluation"
    / "nature-index-publications.tsv"
)


def init_reference_schema(db_path: Path) -> None:
    init_db(db_path)
    with connect(db_path) as connection:
        connection.executescript(REFERENCE_SCHEMA_SQL)


def load_bundled_nature_index(path: Path | None = None) -> dict[str, Any]:
    """Load the user-supplied Nature Index directory bundled with Module 01."""
    source_path = path or BUNDLED_NATURE_INDEX_PATH
    raw = source_path.read_bytes()
    lines = raw.decode("utf-8").splitlines()
    metadata: dict[str, str] = {}
    publications: list[dict[str, Any]] = []
    for line in lines:
        if not line.strip():
            continue
        if line.startswith("# "):
            if ":" in line:
                key, value = line[2:].split(":", 1)
                metadata[key.strip().lower()] = value.strip()
            continue
        parts = line.split("\t")
        if len(parts) not in {3, 4}:
            raise ValueError(f"Invalid bundled Nature Index row: {line[:80]}")
        name, publication_type, article_count = parts[:3]
        restriction_note = parts[3] if len(parts) == 4 else ""
        if publication_type not in {"journal", "conference_proceeding"}:
            raise ValueError(f"Invalid Nature Index publication type: {publication_type}")
        if not article_count.isdigit():
            raise ValueError(f"Invalid Nature Index article count for {name}")
        publications.append({
            "canonical_name": name,
            "publication_type": publication_type,
            "issn": None,
            "eissn": None,
            "restriction_note": restriction_note or None,
        })

    stated_total_match = re.search(r"\d+", metadata.get("stated total", ""))
    if stated_total_match is None:
        raise ValueError("Bundled Nature Index directory has no stated total")
    stated_total = int(stated_total_match.group())
    if len(publications) != stated_total:
        raise ValueError(
            f"Bundled Nature Index directory contains {len(publications)} rows; expected {stated_total}"
        )
    snapshot_date = metadata.get("snapshot date")
    if not snapshot_date or re.fullmatch(r"\d{4}-\d{2}-\d{2}", snapshot_date) is None:
        raise ValueError("Bundled Nature Index snapshot date is missing or invalid")
    source_url = metadata.get("source", "").split(" ", 1)[0]
    if not source_url.startswith("https://www.nature.com/nature-index/"):
        raise ValueError("Bundled Nature Index source must be an official Nature URL")

    journal_count = sum(item["publication_type"] == "journal" for item in publications)
    other_count = len(publications) - journal_count
    return {
        "schema_version": "0.1.0",
        "source_url": source_url,
        "retrieved_at": f"{snapshot_date}T00:00:00+00:00",
        "edition": f"current-12-month-window@{snapshot_date}",
        "content_sha256": hashlib.sha256(raw).hexdigest(),
        "stated_journal_count": journal_count,
        "stated_other_venue_count": other_count,
        "publications": publications,
        "local_source_path": str(source_path.resolve()),
    }


def save_nature_index_snapshot(db_path: Path, topic_run_id: str, payload: dict[str, Any]) -> str:
    init_reference_schema(db_path)
    get_topic_run(db_path, topic_run_id)
    source_url = payload["source_url"]
    digest = payload["content_sha256"]
    if not source_url.startswith("https://www.nature.com/nature-index/"):
        raise ValueError("Nature Index snapshot must identify the official Nature website as its source")
    if re.fullmatch(r"[a-f0-9]{64}", digest) is None:
        raise ValueError("Nature Index content_sha256 must be 64 lowercase hexadecimal characters")
    publications = payload.get("publications", [])
    journal_count = sum(1 for item in publications if item.get("publication_type") == "journal")
    other_count = sum(1 for item in publications if item.get("publication_type") != "journal")
    if journal_count != payload["stated_journal_count"] or other_count != payload["stated_other_venue_count"]:
        raise ValueError("Nature Index stated counts do not match the supplied publication list")

    with connect(db_path) as connection:
        existing = connection.execute(
            "SELECT id FROM nature_index_snapshots WHERE content_sha256 = ?",
            (digest,),
        ).fetchone()
        snapshot_id = str(existing["id"]) if existing else new_id("natureindex")
        if not existing:
            connection.execute(
                """
                INSERT INTO nature_index_snapshots(
                    id, source_url, retrieved_at, edition, content_sha256,
                    stated_journal_count, stated_other_venue_count, publications_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot_id,
                    source_url,
                    payload["retrieved_at"],
                    payload.get("edition"),
                    digest,
                    payload["stated_journal_count"],
                    payload["stated_other_venue_count"],
                    json.dumps(publications, ensure_ascii=False),
                ),
            )
        connection.execute(
            """
            INSERT INTO topic_run_references(topic_run_id, reference_kind, snapshot_id)
            VALUES (?, 'nature_index', ?)
            ON CONFLICT(topic_run_id, reference_kind)
            DO UPDATE SET snapshot_id = excluded.snapshot_id
            """,
            (topic_run_id, snapshot_id),
        )
    return snapshot_id


def attach_bundled_nature_index_snapshot(
    db_path: Path, topic_run_id: str, path: Path | None = None
) -> str:
    return save_nature_index_snapshot(db_path, topic_run_id, load_bundled_nature_index(path))


def normalize_publication_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold().replace("&", " and ")
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return " ".join(normalized.split())


def nature_index_journal_names(snapshot: dict[str, Any]) -> set[str]:
    names = {
        normalize_publication_name(item["canonical_name"])
        for item in snapshot.get("publications", [])
        if item.get("publication_type") == "journal"
    }
    return names


def nature_index_snapshot_for_topic(db_path: Path, topic_run_id: str) -> dict[str, Any] | None:
    init_reference_schema(db_path)
    with connect(db_path) as connection:
        row = connection.execute(
            """
            SELECT s.* FROM topic_run_references r
            JOIN nature_index_snapshots s ON s.id = r.snapshot_id
            WHERE r.topic_run_id = ? AND r.reference_kind = 'nature_index'
            """,
            (topic_run_id,),
        ).fetchone()
    if row is None:
        return None
    result = dict(row)
    result["publications"] = json.loads(result.pop("publications_json"))
    return result
