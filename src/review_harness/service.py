from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import is_research_work, paper_from_openalex, rolling_two_year_window, utc_now
from .openalex import OpenAlexClient
from .storage import (
    finish_search_run,
    frozen_query_for_run,
    set_search_raw_directory,
    start_search_run,
    upsert_and_link_paper,
)


def run_openalex_search(
    *,
    db_path: Path,
    raw_root: Path,
    topic_run_id: str,
    query_id: str,
    max_pages: int = 1,
    per_page: int = 50,
    client: OpenAlexClient | None = None,
) -> dict[str, Any]:
    frozen = frozen_query_for_run(db_path, topic_run_id, query_id)
    query = frozen["query"]
    scope = frozen["scope"]
    if max_pages != 1:
        raise ValueError("Module 01 allows exactly one page per query")
    if not 1 <= per_page <= 50:
        raise ValueError("Module 01 allows at most 50 records per query")
    from_date, to_date = rolling_two_year_window()

    placeholder_raw_directory = raw_root / topic_run_id / "pending"
    search_run_id = start_search_run(
        db_path,
        topic_run_id=topic_run_id,
        query_id=query_id,
        from_date=from_date,
        to_date=to_date,
        max_pages=max_pages,
        raw_directory=placeholder_raw_directory,
    )
    raw_directory = raw_root / topic_run_id / search_run_id
    raw_directory.mkdir(parents=True, exist_ok=False)
    set_search_raw_directory(db_path, search_run_id, raw_directory)

    # Keep the query manifest reproducible without persisting any API key.
    manifest = {
        "schema_version": "0.1.0",
        "search_run_id": search_run_id,
        "topic_run_id": topic_run_id,
        "provider": "openalex",
        "query_id": query_id,
        "scope": scope,
        "query": query,
        "search_scope": "title_and_abstract",
        "from_date": from_date,
        "to_date": to_date,
        "max_pages": max_pages,
        "per_page": per_page,
        "started_at": utc_now(),
    }
    (raw_directory / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    records_received = 0
    non_research_filtered = 0
    unique_papers = 0
    duplicate_links = 0
    client = client or OpenAlexClient()
    try:
        for page in client.search_works(
            query=query,
            from_date=from_date,
            to_date=to_date,
            search_scope="title_and_abstract",
            max_pages=max_pages,
            per_page=per_page,
        ):
            page_number = page["page_number"]
            payload = page["payload"]
            (raw_directory / f"page-{page_number:04d}.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            retrieved_at = utc_now()
            for work in payload.get("results", []):
                records_received += 1
                if not is_research_work(work):
                    non_research_filtered += 1
                    continue
                try:
                    paper = paper_from_openalex(work, retrieved_at)
                except (TypeError, ValueError):
                    continue
                _, is_new = upsert_and_link_paper(
                    db_path,
                    topic_run_id=topic_run_id,
                    search_run_id=search_run_id,
                    scope=scope,
                    paper=paper,
                )
                if is_new:
                    unique_papers += 1
                else:
                    duplicate_links += 1
    except Exception as exc:
        finish_search_run(db_path, search_run_id, records_received=records_received, error=str(exc))
        raise

    finish_search_run(db_path, search_run_id, records_received=records_received)
    return {
        "search_run_id": search_run_id,
        "topic_run_id": topic_run_id,
        "query_id": query_id,
        "scope": scope,
        "records_received": records_received,
        "non_research_records_filtered": non_research_filtered,
        "new_unique_papers": unique_papers,
        "matched_existing_papers": duplicate_links,
        "raw_directory": str(raw_directory.resolve()),
    }
