from __future__ import annotations

import hashlib
import json
from typing import Any

from .models import SEARCH_QUERY_LIMITS, normalize_title


def normalize_topic_key(topic: str, profile: dict[str, Any] | None = None) -> str:
    canonical = ((profile or {}).get("topic") or {}).get("canonical_zh") or topic
    return normalize_title(str(canonical))


def canonicalize_query_plan(queries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not 1 <= len(queries) <= sum(SEARCH_QUERY_LIMITS.values()):
        raise ValueError("A frozen query plan requires between 1 and 6 queries")
    seen_ids: set[str] = set()
    scope_counts = {scope: 0 for scope in SEARCH_QUERY_LIMITS}
    canonical: list[dict[str, Any]] = []
    for raw in queries:
        query_id = str(raw.get("id") or "").strip()
        scope = str(raw.get("scope") or "").strip()
        provider = str(raw.get("provider") or "").strip()
        query = " ".join(str(raw.get("query") or "").split())
        if not query_id or query_id in seen_ids:
            raise ValueError("Frozen query ids must be non-empty and unique")
        if scope not in SEARCH_QUERY_LIMITS:
            raise ValueError(f"Invalid frozen query scope: {scope}")
        if provider != "openalex":
            raise ValueError("Module 01 frozen queries must use OpenAlex")
        if not query:
            raise ValueError(f"Frozen query {query_id} is empty")
        scope_counts[scope] += 1
        if scope_counts[scope] > SEARCH_QUERY_LIMITS[scope]:
            raise ValueError(
                f"Frozen query plan allows at most {SEARCH_QUERY_LIMITS[scope]} {scope} queries"
            )
        seen_ids.add(query_id)
        item = {"id": query_id, "scope": scope, "provider": provider, "query": query}
        if raw.get("notes"):
            item["notes"] = str(raw["notes"])
        canonical.append(item)
    order = {"direct": 0, "technical": 1}
    return sorted(canonical, key=lambda item: (order[item["scope"]], item["id"]))


def query_plan_sha256(queries: list[dict[str, Any]]) -> str:
    stable = [
        {key: item[key] for key in ("id", "scope", "provider", "query")}
        for item in canonicalize_query_plan(queries)
    ]
    encoded = json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def query_by_id(queries: list[dict[str, Any]], query_id: str) -> dict[str, Any]:
    for item in canonicalize_query_plan(queries):
        if item["id"] == query_id:
            return item
    raise KeyError(f"Unknown frozen query id: {query_id}")


def build_review_query_plan(queries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Derive Module 02 discovery queries from the frozen Module 01 plan."""
    canonical = canonicalize_query_plan(queries)
    seeds = [item for item in canonical if item["scope"] == "direct"][:2]
    if not seeds:
        seeds = canonical[:2]
    plan: list[dict[str, Any]] = []
    for index, seed in enumerate(seeds, start=1):
        plan.append({
            "id": f"review-typed-{index:02d}",
            "query": seed["query"],
            "typed_only": True,
            "source_query_id": seed["id"],
        })
    for index, seed in enumerate(seeds, start=1):
        query = seed["query"]
        if not any(token in query.casefold() for token in ("review", "progress", "advances", "perspective", "outlook")):
            query = f"{query} review"
        plan.append({
            "id": f"review-intent-{index:02d}",
            "query": query,
            "typed_only": False,
            "source_query_id": seed["id"],
        })
    return plan


def review_query_plan_sha256(plan: list[dict[str, Any]]) -> str:
    encoded = json.dumps(plan, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
