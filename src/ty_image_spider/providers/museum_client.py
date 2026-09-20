"""博物馆公开 JSON 接口的受限读取与短时缓存，不负责来源数据解析。"""

from __future__ import annotations

import json
import re
from http.client import HTTPException
from typing import Any, Callable, Mapping
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from ..cache import JsonCache
from ..models import SpiderError
from ..security import read_limited, require_https_host


_ENDPOINTS = {
    "artic": ("https://api.artic.edu/api/v1/", "芝加哥艺术博物馆"),
    "vam": ("https://api.vam.ac.uk/v2/", "V&A"),
    "cleveland": ("https://openaccess-api.clevelandart.org/api/", "克利夫兰艺术博物馆"),
}


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


class MuseumClient:
    def __init__(
        self,
        source: str,
        cache: JsonCache | None = None,
        open_url: Callable[..., Any] | None = None,
    ) -> None:
        self._base, self._label = _ENDPOINTS[source]
        self._source = source
        self._cache = cache
        self._open_url = open_url or build_opener(_NoRedirect()).open

    def get(
        self, path: str, params: Mapping[str, object], *, refresh: bool = False
    ) -> dict[str, Any]:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9/_-]*", path):
            raise SpiderError("invalid_endpoint", "馆藏接口路径无效")
        url = self._base + path + "?" + urlencode(sorted(params.items()))
        cached = self._cache.get(url, 300) if self._cache and not refresh else None
        if isinstance(cached, dict):
            return cached
        request = Request(
            url,
            headers={"User-Agent": "TY-Image-Spider/2.1", "Accept": "application/json"},
        )
        try:
            with self._open_url(request, timeout=25) as response:
                require_https_host(
                    response.geturl(),
                    lambda host: host == urlsplit(self._base).hostname,
                )
                data = json.loads(read_limited(response, 8 * 1024 * 1024))
            if not isinstance(data, dict):
                raise ValueError("expected JSON object")
        except HTTPError as exc:
            message = (
                "请求过于频繁，请稍后重试"
                if exc.code == 429
                else "暂时无法访问，请稍后重试"
            )
            raise SpiderError(
                f"{self._source}_unavailable", self._label + message, status=502
            ) from None
        except (OSError, HTTPException) as exc:
            raise SpiderError(
                f"{self._source}_unavailable",
                self._label + "连接失败，请稍后重试",
                status=502,
            ) from exc
        except (ValueError, UnicodeError) as exc:
            raise SpiderError(
                f"{self._source}_invalid_response",
                self._label + "返回数据无效",
                status=502,
            ) from exc
        if self._cache:
            self._cache.put(url, data)
        return data
