from __future__ import annotations

import re
import unicodedata
from datetime import UTC, date, datetime
from typing import Any
from uuid import uuid4

SCHEMA_VERSION = "0.1.0"
VALID_SCOPES = {"direct", "technical"}
VALID_DECISIONS = {"approved", "rejected"}
VALID_RECOMMENDATIONS = {
    "recommended",
    "reframe_required",
    "insufficient_evidence",
    "not_recommended",
    "pending",
}
SEARCH_QUERY_LIMITS = {"direct": 3, "technical": 3}
MAX_TOPIC_SEARCHES = 6
RESEARCH_WORK_TYPES = {"article", "preprint", "conference-paper", "proceedings-article"}


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def rolling_two_year_window(as_of: date | None = None) -> tuple[str, str]:
    end = as_of or datetime.now(UTC).date()
    try:
        start = end.replace(year=end.year - 2)
    except ValueError:
        # 29 February maps to 28 February when the start year is not a leap year.
        start = end.replace(year=end.year - 2, day=28)
    return start.isoformat(), end.isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def normalize_doi(value: str | None) -> str | None:
    if not value:
        return None
    doi = value.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.startswith(prefix):
            doi = doi[len(prefix) :]
            break
    return doi or None


def normalize_title(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = re.sub(r"[^\w\s]", " ", normalized, flags=re.UNICODE)
    return " ".join(normalized.split())


def abstract_from_inverted_index(index: dict[str, list[int]] | None) -> str | None:
    if not index:
        return None
    positions: list[tuple[int, str]] = []
    for token, token_positions in index.items():
        positions.extend((position, token) for position in token_positions)
    positions.sort(key=lambda item: item[0])
    return " ".join(token for _, token in positions) or None


def is_research_work(work: dict[str, Any]) -> bool:
    work_type = str(work.get("type") or "").strip().casefold()
    return work_type in RESEARCH_WORK_TYPES


def paper_from_openalex(work: dict[str, Any], retrieved_at: str) -> dict[str, Any]:
    title = (work.get("title") or "").strip()
    if not title:
        raise ValueError("OpenAlex work has no title")

    publication_year = work.get("publication_year")
    if not isinstance(publication_year, int) or not 1600 <= publication_year <= 2200:
        raise ValueError("OpenAlex work has no valid publication year")

    primary_location = work.get("primary_location") or {}
    source = primary_location.get("source") or {}
    openalex_id = work.get("id")
    paper_id = openalex_id.rsplit("/", 1)[-1] if openalex_id else new_id("paper")

    return {
        "schema_version": SCHEMA_VERSION,
        "paper_id": paper_id,
        "openalex_id": openalex_id,
        "doi": normalize_doi(work.get("doi")),
        "title": title,
        "normalized_title": normalize_title(title),
        "abstract": abstract_from_inverted_index(work.get("abstract_inverted_index")),
        "publication_date": work.get("publication_date"),
        "publication_year": publication_year,
        "work_type": work.get("type") or "unknown",
        "source_name": source.get("display_name"),
        "issn_l": source.get("issn_l"),
        "cited_by_count": work.get("cited_by_count"),
        "source_provider": "openalex",
        "retrieved_at": retrieved_at,
    }
