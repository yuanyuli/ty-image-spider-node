"""NASA Image and Video Library 视频搜索与清单客户端。"""

from __future__ import annotations

import json
from typing import Any, Callable, Mapping
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from ....domain import SpiderError
from ....infrastructure.cache import JsonCache
from ....infrastructure.network_retry import retry_call
from ....infrastructure.security import read_limited, require_https_host
from ....version import USER_AGENT


_SEARCH_URL = "https://images-api.nasa.gov/search"


class NasaVideoClient:
    def __init__(
        self,
        cache: JsonCache | None = None,
        open_url: Callable[..., Any] = urlopen,
    ) -> None:
        self._cache = cache
        self._open_url = open_url

    def search(
        self, query: str, page: int, refresh: bool = False
    ) -> Mapping[str, object]:
        if page < 1 or page > 10000:
            raise SpiderError("invalid_cursor", "NASA 视频分页游标无效")
        params: dict[str, object] = {
            "media_type": "video",
            "page": page,
            "page_size": 24,
        }
        if query.strip():
            params["q"] = query.strip()
        data = self._get(
            _SEARCH_URL + "?" + urlencode(sorted(params.items())),
            lambda host: host == "images-api.nasa.gov",
            refresh,
        )
        if not isinstance(data, Mapping):
            raise SpiderError("nasa_video_invalid", "NASA 视频搜索结果无效", status=502)
        return data

    def manifest(self, url: str, refresh: bool = False) -> list[str]:
        self._require_manifest_url(url)
        data = self._get(url, lambda host: host == "images-assets.nasa.gov", refresh)
        if not isinstance(data, list):
            raise SpiderError("nasa_video_invalid", "NASA 视频清单无效", status=502)
        return [value for value in data if isinstance(value, str)]

    def _get(
        self,
        url: str,
        host_rule: Callable[[str], bool],
        refresh: bool,
    ) -> object:
        cached = self._cache.get(url, 300) if self._cache and not refresh else None
        if cached is not None:
            return cached
        request = Request(
            url, headers={"Accept": "application/json", "User-Agent": USER_AGENT}
        )

        def fetch() -> object:
            with self._open_url(request, timeout=30) as response:
                require_https_host(response.geturl(), host_rule)
                return json.loads(read_limited(response, 16 * 1024 * 1024))

        try:
            result = retry_call(fetch)
        except SpiderError:
            raise
        except (OSError, TimeoutError, ValueError, UnicodeError) as exc:
            raise SpiderError(
                "nasa_video_unavailable", "NASA 视频服务暂时不可用", status=502
            ) from exc
        if self._cache:
            self._cache.put(url, result)
        return result

    @staticmethod
    def _require_manifest_url(url: str) -> None:
        try:
            parsed = urlsplit(url)
            valid = (
                parsed.scheme == "https"
                and parsed.hostname == "images-assets.nasa.gov"
                and parsed.port in {None, 443}
                and parsed.username is None
                and parsed.password is None
                and parsed.path.endswith("/collection.json")
            )
        except ValueError:
            valid = False
        if not valid:
            raise SpiderError("unsafe_url", "NASA 视频清单地址无效")
