from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import is_research_work, paper_from_openalex, utc_now
from .module02_storage import (
    finish_module02_search,
    frozen_review_query_for_run,
    get_module02_run,
    plan_module02_research_queries,
    set_module02_search_raw_directory,
    start_module02_search,
    upsert_module02_research,
    upsert_review,
)
from .openalex import OpenAlexClient


def _raw_directory(raw_root: Path, module02_run_id: str, search_id: str) -> Path:
    path = raw_root / module02_run_id / search_id
    path.mkdir(parents=True, exist_ok=False)
    return path


def _write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def _review_from_openalex(work: dict[str, Any], observed_at: str) -> dict[str, Any]:
    record = paper_from_openalex(work, observed_at)
    primary_location = work.get("primary_location") or {}
    doi = record.get("doi")
    paper_url = (
        f"https://doi.org/{doi}"
        if doi
        else primary_location.get("landing_page_url") or record.get("openalex_id")
    )
    if not paper_url:
        raise ValueError("Review has no stable paper link")
    return {
        "openalex_id": record.get("openalex_id"),
        "doi": doi,
        "title": record["title"],
        "normalized_title": record["normalized_title"],
        "abstract": record.get("abstract"),
        "publication_date": record.get("publication_date"),
        "publication_year": record["publication_year"],
        "journal": record.get("source_name"),
        "issn_l": record.get("issn_l"),
        "cited_by_count": record.get("cited_by_count"),
        "citation_as_of": observed_at,
        "paper_url": paper_url,
        "provider_work_type": record["work_type"],
    }


def run_review_search(
    *,
    db_path: Path,
    raw_root: Path,
    module02_run_id: str,
    query_id: str,
    per_page: int = 100,
    max_pages: int = 10,
    client: OpenAlexClient | None = None,
) -> dict[str, Any]:
    frozen = frozen_review_query_for_run(db_path, module02_run_id, query_id)
    query = frozen["query"]
    typed_only = bool(frozen["typed_only"])
    if not 1 <= per_page <= 100:
        raise ValueError("Module 02 review search allows at most 100 records per page")
    if not 1 <= max_pages <= 10:
        raise ValueError("Module 02 review search allows at most 10 pages")
    placeholder = raw_root / module02_run_id / "pending"
    search_id = start_module02_search(
        db_path,
        module02_run_id=module02_run_id,
        phase="reviews",
        query_id=query_id,
        scope="review",
        query=query,
        from_date=None,
        to_date=None,
        work_type_filter="review" if typed_only else "review_intent_untyped",
        raw_directory=placeholder,
    )
    raw_directory = _raw_directory(raw_root, module02_run_id, search_id)
    set_module02_search_raw_directory(db_path, search_id, raw_directory)
    observed_at = utc_now()
    _write_manifest(
        raw_directory / "manifest.json",
        {
            "schema_version": "0.1.0",
            "module02_run_id": module02_run_id,
            "search_id": search_id,
            "query_id": query_id,
            "phase": "reviews",
            "query": query,
            "work_type_filter": "review" if typed_only else "review_intent_untyped",
            "per_page": per_page,
            "max_pages": max_pages,
            "search_scope": "title_and_abstract",
            "started_at": observed_at,
        },
    )

    received = 0
    retained = 0
    provider_total: int | None = None
    client = client or OpenAlexClient()
    try:
        for page in client.search_works(
            query=query,
            work_type="review" if typed_only else None,
            sort="publication_date:desc",
            search_scope="title_and_abstract",
            max_pages=max_pages,
            per_page=per_page,
        ):
            payload = page["payload"]
            provider_total = (payload.get("meta") or {}).get("count", provider_total)
            (raw_directory / f"page-{page['page_number']:04d}.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            for work in payload.get("results", []):
                received += 1
                try:
                    review = _review_from_openalex(work, observed_at)
                except (TypeError, ValueError):
                    continue
                _, is_new = upsert_review(db_path, module02_run_id, review)
                if is_new:
                    retained += 1
    except Exception as exc:
        finish_module02_search(
            db_path,
            search_id,
            records_received=received,
            records_retained=retained,
            provider_total=provider_total,
            truncated=provider_total is not None and received < provider_total,
            error=str(exc),
        )
        raise

    finish_module02_search(
        db_path,
        search_id,
        records_received=received,
        records_retained=retained,
        provider_total=provider_total,
        truncated=provider_total is not None and received < provider_total,
    )
    return {
        "module02_run_id": module02_run_id,
        "search_id": search_id,
        "query_id": query_id,
        "search_mode": "typed_review" if typed_only else "review_intent_untyped",
        "records_received": received,
        "provider_total": provider_total,
        "truncated": provider_total is not None and received < provider_total,
        "new_reviews_retained": retained,
        "raw_directory": str(raw_directory.resolve()),
    }


def run_post_review_research_search(
    *,
    db_path: Path,
    raw_root: Path,
    module02_run_id: str,
    query_id: str,
    per_page: int = 100,
    max_pages: int = 10,
    client: OpenAlexClient | None = None,
) -> dict[str, Any]:
    if not 1 <= per_page <= 100:
        raise ValueError("Module 02 research search allows at most 100 records per page")
    if not 1 <= max_pages <= 10:
        raise ValueError("Module 02 research search allows at most 10 pages")
    run = get_module02_run(db_path, module02_run_id)
    from_date = run.get("research_from_date")
    to_date = run.get("research_to_date")
    if not from_date or not to_date:
        raise ValueError("Finalize the newest-review anchor before searching research papers")
    plan = next(
        (
            item for item in plan_module02_research_queries(db_path, module02_run_id)
            if item["id"] == query_id
        ),
        None,
    )
    if plan is None:
        raise ValueError("Unknown frozen TopicProfile query id for Module 02 research")
    query = plan["query"]
    scope = plan["scope"]
    if plan["action"] != "supplement":
        raise ValueError(f"Research query does not need retrieval: {plan['action']}")

    placeholder = raw_root / module02_run_id / "pending"
    search_id = start_module02_search(
        db_path,
        module02_run_id=module02_run_id,
        phase="research",
        query_id=query_id,
        scope=scope,
        query=query,
        from_date=from_date,
        to_date=to_date,
        work_type_filter="original_research",
        raw_directory=placeholder,
    )
    raw_directory = _raw_directory(raw_root, module02_run_id, search_id)
    set_module02_search_raw_directory(db_path, search_id, raw_directory)
    observed_at = utc_now()
    _write_manifest(
        raw_directory / "manifest.json",
        {
            "schema_version": "0.1.0",
            "module02_run_id": module02_run_id,
            "search_id": search_id,
            "phase": "research",
            "query_id": query_id,
            "scope": scope,
            "query": query,
            "from_date": from_date,
            "to_date": to_date,
            "work_type_filter": "original_research",
            "per_page": per_page,
            "max_pages": max_pages,
            "search_scope": "title_and_abstract",
            "started_at": observed_at,
        },
    )

    received = 0
    retained = 0
    filtered = 0
    provider_total: int | None = None
    client = client or OpenAlexClient()
    try:
        for page in client.search_works(
            query=query,
            from_date=from_date,
            to_date=to_date,
            sort="publication_date:desc",
            search_scope="title_and_abstract",
            max_pages=max_pages,
            per_page=per_page,
        ):
            payload = page["payload"]
            provider_total = (payload.get("meta") or {}).get("count", provider_total)
            (raw_directory / f"page-{page['page_number']:04d}.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            for work in payload.get("results", []):
                received += 1
                if not is_research_work(work):
                    filtered += 1
                    continue
                try:
                    paper = paper_from_openalex(work, observed_at)
                except (TypeError, ValueError):
                    continue
                _, is_new = upsert_module02_research(
                    db_path,
                    module02_run_id,
                    paper,
                    origin="module02",
                    scope=scope,
                )
                if is_new:
                    retained += 1
    except Exception as exc:
        finish_module02_search(
            db_path,
            search_id,
            records_received=received,
            records_retained=retained,
            provider_total=provider_total,
            truncated=provider_total is not None and received < provider_total,
            error=str(exc),
        )
        raise

    finish_module02_search(
        db_path,
        search_id,
        records_received=received,
        records_retained=retained,
        provider_total=provider_total,
        truncated=provider_total is not None and received < provider_total,
    )
    return {
        "module02_run_id": module02_run_id,
        "search_id": search_id,
        "query_id": query_id,
        "scope": scope,
        "research_from_date": from_date,
        "research_to_date": to_date,
        "records_received": received,
        "provider_total": provider_total,
        "truncated": provider_total is not None and received < provider_total,
        "non_research_records_filtered": filtered,
        "new_research_records": retained,
        "raw_directory": str(raw_directory.resolve()),
    }
