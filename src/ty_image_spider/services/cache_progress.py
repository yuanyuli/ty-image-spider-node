"""按来源、搜索词与筛选条件保存批量缓存遍历断点。"""

from __future__ import annotations

import json
from typing import Mapping

from ..cache import JsonCache


class CacheProgress:
    def __init__(self, cache: JsonCache) -> None:
        self._cache = cache

    @staticmethod
    def _key(request: Mapping[str, object]) -> str:
        return json.dumps(dict(request), sort_keys=True, ensure_ascii=False)

    def load(self, request: Mapping[str, object]) -> str | None:
        value = self._cache.get(self._key(request), None)
        return value if isinstance(value, str) else None

    def save(self, request: Mapping[str, object], cursor: str | None) -> None:
        self._cache.put(self._key(request), cursor)

    def clear(self, request: Mapping[str, object]) -> None:
        self._cache.clear(self._key(request))
