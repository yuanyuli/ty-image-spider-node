"""电影文章缓存：跨静帧分页复用，并在来源失败时回退。"""

from __future__ import annotations

import json
import time
from typing import Any, Mapping

from ..cache import JsonCache
from ..models import SpiderError
from .curated_client import FilmGrabClient


class FilmGrabArticles:
    def __init__(self, client: FilmGrabClient, cache: JsonCache | None) -> None:
        self._client = client
        self._cache = cache

    def read(
        self, query: str, page: int, refresh: bool = False, post_id: int | None = None
    ) -> tuple[list[Mapping[str, Any]], int, bool]:
        key = json.dumps(["exact-film-v3", query, page, post_id], ensure_ascii=False)
        saved = self._cache.get(key, None) if self._cache else None
        if not (
            isinstance(saved, dict)
            and isinstance(saved.get("posts"), list)
            and isinstance(saved.get("last_page"), int)
            and isinstance(saved.get("fetched_at"), (int, float))
        ):
            saved = None
        if saved and not refresh and time.time() - saved["fetched_at"] < 300:
            return saved["posts"], saved["last_page"], False
        try:
            posts, last_page = (
                self._client.posts(query, page, post_id=post_id)
                if post_id
                else self._client.posts(query, page)
            )
        except SpiderError:
            if saved is None:
                raise
            return saved["posts"], saved["last_page"], True
        if self._cache:
            self._cache.put(
                key,
                {"posts": posts, "last_page": last_page, "fetched_at": time.time()},
            )
        return posts, last_page, False
