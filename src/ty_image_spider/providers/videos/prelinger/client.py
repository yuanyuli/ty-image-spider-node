"""Internet Archive Prelinger 搜索与详情客户端。"""

from __future__ import annotations

import json
from typing import Any, Callable, Mapping
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from ....domain import SpiderError
from ....infrastructure.cache import JsonCache
from ....infrastructure.network_retry import retry_call
from ....infrastructure.security import read_limited, require_https_host
from ....version import USER_AGENT


_SEARCH_URL = "https://archive.org/advancedsearch.php"
_METADATA_URL = "https://archive.org/metadata/"
_SORTS = {
    "popular": "downloads desc",
    "newest": "date desc",
    "oldest": "date asc",
    "relevance": "_score desc",
}


class PrelingerClient:
    def __init__(
        self,
        cache: JsonCache | None = None,
        open_url: Callable[..., Any] = urlopen,
    ) -> None:
        self._cache = cache
        self._open_url = open_url

    def search(
        self,
        query: str,
        page: int,
        sort: str,
        refresh: bool = False,
    ) -> Mapping[str, object]:
        if page < 1 or sort not in _SORTS:
            raise SpiderError("invalid_search", "Prelinger 搜索参数无效")
        terms = "collection:prelinger AND mediatype:movies"
        if query:
            escaped = query.replace('"', " ").strip()
            terms += f' AND ({escaped})'
        params = {
            "q": terms,
            "fl[]": "identifier,title,creator,date,description,downloads,item_size",
            "rows": 24,
            "page": page,
            "sort[]": _SORTS[sort],
            "output": "json",
        }
        return self._get(_SEARCH_URL + "?" + urlencode(params, doseq=True), refresh)

    def metadata(
        self, identifier: str, refresh: bool = False
    ) -> Mapping[str, object]:
        if not identifier or len(identifier) > 128:
            raise SpiderError("invalid_asset", "Prelinger 素材 ID 无效")
        return self._get(_METADATA_URL + quote(identifier, safe=""), refresh)

    def _get(self, url: str, refresh: bool) -> Mapping[str, object]:
        cached = self._cache.get(url, 300) if self._cache and not refresh else None
        if isinstance(cached, Mapping):
            return cached
        request = Request(
            url, headers={"Accept": "application/json", "User-Agent": USER_AGENT}
        )

        def fetch() -> Mapping[str, object]:
            with self._open_url(request, timeout=30) as response:
                require_https_host(response.geturl(), lambda host: host == "archive.org")
                data = json.loads(read_limited(response, 16 * 1024 * 1024))
            if not isinstance(data, Mapping):
                raise ValueError("invalid JSON root")
            return data

        try:
            result = retry_call(fetch)
        except SpiderError:
            raise
        except (OSError, TimeoutError, ValueError, UnicodeError) as exc:
            raise SpiderError(
                "prelinger_unavailable", "Prelinger Archives 暂时不可用", status=502
            ) from exc
        if self._cache:
            self._cache.put(url, dict(result))
        return result
