"""Wikimedia Commons 视频搜索与详情客户端。"""

from __future__ import annotations

import json
from typing import Any, Callable, Mapping
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ....domain import SpiderError
from ....infrastructure.cache import JsonCache
from ....infrastructure.network_retry import retry_call
from ....infrastructure.security import read_limited, require_https_host
from ....version import USER_AGENT


_API = "https://commons.wikimedia.org/w/api.php"
CATEGORIES = {
    "all": "",
    "film": "incategory:Films",
    "animation": "incategory:Animations",
    "science": "incategory:Videos of science",
    "nature": "incategory:Nature videos",
}
_VIDEO_INFO = "url|size|mime|mediatype|extmetadata|derivatives|duration"


class CommonsVideoClient:
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
        category: str,
        cursor: str | None,
        refresh: bool = False,
    ) -> Mapping[str, object]:
        if category not in CATEGORIES:
            raise SpiderError("invalid_category", "Commons 视频分类无效")
        offset = None
        if cursor is not None:
            if not cursor.startswith("s:") or not cursor[2:].isdigit():
                raise SpiderError("invalid_cursor", "Commons 视频分页游标无效")
            offset = cursor[2:]
        terms = " ".join(
            value
            for value in (query.strip(), CATEGORIES[category], "filetype:video")
            if value
        )
        params: dict[str, object] = {
            "action": "query",
            "format": "json",
            "formatversion": 2,
            "generator": "search",
            "gsrsearch": terms,
            "gsrnamespace": 6,
            "gsrlimit": 24,
            "prop": "videoinfo",
            "viprop": _VIDEO_INFO,
            "viurlwidth": 800,
        }
        if offset is not None:
            params["gsroffset"] = offset
        return self._get(params, refresh)

    def detail(self, title: str, refresh: bool = False) -> Mapping[str, object]:
        if not title.startswith("File:") or len(title) > 512:
            raise SpiderError("invalid_asset", "Commons 视频标题无效")
        return self._get(
            {
                "action": "query",
                "format": "json",
                "formatversion": 2,
                "titles": title,
                "prop": "videoinfo",
                "viprop": _VIDEO_INFO,
                "viurlwidth": 800,
            },
            refresh,
        )

    def _get(
        self, params: Mapping[str, object], refresh: bool
    ) -> Mapping[str, object]:
        url = _API + "?" + urlencode(sorted(params.items()))
        cached = self._cache.get(url, 300) if self._cache and not refresh else None
        if isinstance(cached, Mapping):
            return cached
        request = Request(
            url, headers={"Accept": "application/json", "User-Agent": USER_AGENT}
        )

        def fetch() -> Mapping[str, object]:
            with self._open_url(request, timeout=30) as response:
                require_https_host(
                    response.geturl(), lambda host: host == "commons.wikimedia.org"
                )
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
                "commons_video_unavailable",
                "Wikimedia Commons 视频暂时不可用",
                status=502,
            ) from exc
        if self._cache:
            self._cache.put(url, dict(result))
        return result

