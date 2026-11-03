from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

OPENALEX_WORKS_URL = "https://api.openalex.org/works"
DEFAULT_OPENALEX_KEY_FILE = Path("OPENALEX_API_KEY.txt")


def load_openalex_api_key(key_file: Path | None = None) -> str | None:
    environment_value = os.getenv("OPENALEX_API_KEY")
    if environment_value and environment_value.strip():
        return environment_value.strip()

    configured_path = os.getenv("OPENALEX_API_KEY_FILE")
    path = key_file or (Path(configured_path) if configured_path else DEFAULT_OPENALEX_KEY_FILE)
    if not path.exists():
        return None
    if path.is_symlink():
        raise ValueError("OpenAlex key file must not be a symbolic link")
    if not path.is_file():
        raise ValueError("OpenAlex key path is not a regular file")

    lines = [line.strip() for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    if len(lines) != 1:
        raise ValueError("OpenAlex key file must contain exactly one non-empty line")
    if any(character.isspace() for character in lines[0]):
        raise ValueError("OpenAlex key must not contain whitespace")
    return lines[0]


class OpenAlexClient:
    def __init__(self, *, api_key: str | None = None, mailto: str | None = None, timeout: int = 60):
        self.api_key = api_key.strip() if api_key is not None and api_key.strip() else load_openalex_api_key()
        self.mailto = mailto if mailto is not None else os.getenv("OPENALEX_MAILTO")
        self.timeout = timeout

    def search_works(
        self,
        *,
        query: str,
        from_date: str | None = None,
        to_date: str | None = None,
        work_type: str | None = None,
        sort: str | None = None,
        search_scope: str = "all",
        max_pages: int = 1,
        per_page: int = 100,
    ) -> Iterator[dict[str, Any]]:
        if not query.strip():
            raise ValueError("query must not be empty")
        if max_pages < 1:
            raise ValueError("max_pages must be at least 1")
        if search_scope not in {"all", "title_and_abstract"}:
            raise ValueError("search_scope must be all or title_and_abstract")
        if (from_date is None) != (to_date is None):
            raise ValueError("from_date and to_date must be supplied together")
        if not 1 <= per_page <= 100:
            raise ValueError("per_page must be between 1 and 100")

        cursor = "*"
        for page_number in range(1, max_pages + 1):
            filters: list[str] = []
            if from_date is not None and to_date is not None:
                filters.extend([
                    f"from_publication_date:{from_date}",
                    f"to_publication_date:{to_date}",
                ])
            if work_type:
                filters.append(f"type:{work_type}")

            search_parameter = "search" if search_scope == "all" else "search.title_and_abstract"
            params = {
                search_parameter: query,
                "per-page": str(per_page),
                "cursor": cursor,
            }
            if filters:
                params["filter"] = ",".join(filters)
            if sort:
                params["sort"] = sort
            if self.mailto:
                params["mailto"] = self.mailto

            headers = {
                "Accept": "application/json",
                "User-Agent": "research-review-harness/0.3.0",
            }
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            request = Request(
                f"{OPENALEX_WORKS_URL}?{urlencode(params)}",
                headers=headers,
            )
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.load(response)

            yield {
                "page_number": page_number,
                "payload": payload,
            }

            cursor = (payload.get("meta") or {}).get("next_cursor")
            if not cursor or not payload.get("results"):
                break
