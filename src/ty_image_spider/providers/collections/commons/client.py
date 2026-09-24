"""Wikimedia Commons API 客户端。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ....domain import SpiderError
from ....infrastructure.cache import JsonCache
from ....infrastructure.network_retry import retry_call
from ....infrastructure.security import read_limited, require_https_host
from ....version import USER_AGENT


_API = "https://commons.wikimedia.org/w/api.php"
CATEGORIES = {
    "featured": ("精选图片", "Category:Featured pictures on Wikimedia Commons"),
    "quality": ("优质图片", "Category:Quality images"),
    "photography": (
        "精选摄影",
        "Category:Featured photographs in the public domain",
    ),
    "art": ("艺术作品", "Category:Quality images of works of art"),
}


@dataclass(frozen=True, slots=True)
class CommonsPage:
    items: tuple[Mapping[str, Any], ...]
    next_cursor: str | None = None


class CommonsClient:
    def __init__(
        self,
        cache: JsonCache | None = None,
        open_url: Callable[..., Any] = urlopen,
    ) -> None:
        self._cache = cache
        self._open_url = open_url

    def search(self, query: str, category: str, cursor: str | None) -> CommonsPage:
        if category not in CATEGORIES:
            raise SpiderError("invalid_category", "Commons 分类无效")
        params: dict[str, object] = {
            "action": "query",
            "format": "json",
            "formatversion": 2,
            "prop": "imageinfo",
            "iiprop": "url|size|extmetadata",
            "iiurlwidth": 800,
        }
        if query:
            params.update(
                generator="search",
                gsrsearch=f"{query} incategory:{CATEGORIES[category][1][9:]}",
                gsrnamespace=6,
                gsrlimit=24,
            )
            if cursor:
                if not cursor.startswith("s:") or not cursor[2:].isdigit():
                    raise SpiderError("invalid_cursor", "Commons 分页游标无效")
                params["gsroffset"] = cursor[2:]
        else:
            params.update(
                generator="categorymembers",
                gcmtitle=CATEGORIES[category][1],
                gcmtype="file",
                gcmlimit=24,
            )
            if cursor:
                if not cursor.startswith("g:") or len(cursor) > 2048:
                    raise SpiderError("invalid_cursor", "Commons 分页游标无效")
                params["gcmcontinue"] = cursor[2:]
        data = self._get(params)
        query_data = data.get("query")
        pages = query_data.get("pages") if isinstance(query_data, Mapping) else []
        rows = (
            tuple(row for row in pages if isinstance(row, Mapping))
            if isinstance(pages, list)
            else ()
        )
        continuation = data.get("continue")
        next_cursor = None
        if isinstance(continuation, Mapping):
            if isinstance(continuation.get("gsroffset"), int):
                next_cursor = f"s:{continuation['gsroffset']}"
            elif isinstance(continuation.get("gcmcontinue"), str):
                next_cursor = "g:" + continuation["gcmcontinue"]
        return CommonsPage(rows, next_cursor)

    def file(self, page_id: int) -> Mapping[str, Any]:
        if page_id < 1:
            raise SpiderError("invalid_asset", "Commons 素材 ID 无效")
        data = self._get(
            {
                "action": "query",
                "format": "json",
                "formatversion": 2,
                "pageids": page_id,
                "prop": "imageinfo",
                "iiprop": "url|size|extmetadata",
                "iiurlwidth": 800,
            }
        )
        query_data = data.get("query")
        pages = query_data.get("pages") if isinstance(query_data, Mapping) else []
        if (
            not isinstance(pages, list)
            or not pages
            or not isinstance(pages[0], Mapping)
        ):
            raise SpiderError("commons_not_found", "Commons 图片不存在", status=404)
        return pages[0]

    def _get(self, params: Mapping[str, object]) -> Mapping[str, Any]:
        url = _API + "?" + urlencode(sorted(params.items()))
        cached = self._cache.get(url, 300) if self._cache else None
        if isinstance(cached, Mapping):
            return cached
        request = Request(
            url,
            headers={"Accept": "application/json", "User-Agent": USER_AGENT},
        )

        def fetch() -> Mapping[str, Any]:
            with self._open_url(request, timeout=30) as response:
                require_https_host(
                    response.geturl(), lambda host: host == "commons.wikimedia.org"
                )
                data = json.loads(read_limited(response, 12 * 1024 * 1024))
            if not isinstance(data, Mapping):
                raise ValueError("invalid root")
            return data

        try:
            data = retry_call(fetch)
        except HTTPError as exc:
            raise SpiderError(
                "commons_http_error", f"Commons 请求失败（{exc.code}）", status=502
            ) from exc
        except (URLError, TimeoutError, OSError, ValueError, UnicodeError) as exc:
            raise SpiderError(
                "commons_unavailable", "Wikimedia Commons 暂时不可用", status=502
            ) from exc
        if self._cache:
            self._cache.put(url, dict(data))
        return data
