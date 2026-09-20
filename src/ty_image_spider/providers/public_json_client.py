"""策展公开 JSON 的受限读取与缓存，保留分页响应头。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from http.client import HTTPException
from typing import Any, Callable, Mapping
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from ..cache import JsonCache
from ..models import SpiderError
from ..security import read_limited, require_https_host


@dataclass(frozen=True)
class JsonResponse:
    data: Any
    total_pages: int = 0


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


class PublicJsonClient:
    def __init__(
        self,
        base_url: str,
        label: str,
        cache: JsonCache | None = None,
        open_url: Callable[..., Any] | None = None,
    ) -> None:
        self._base = base_url
        self._label = label
        self._cache = cache
        self._open_url = open_url or build_opener(_NoRedirect()).open

    def get(
        self, path: str, params: Mapping[str, object], *, refresh: bool = False
    ) -> JsonResponse:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9/_-]*", path):
            raise SpiderError("invalid_endpoint", "素材接口路径无效")
        url = self._base + path + "?" + urlencode(sorted(params.items()))
        cached = self._cache.get(url, 300) if self._cache and not refresh else None
        if isinstance(cached, dict) and "data" in cached:
            return JsonResponse(cached["data"], int(cached.get("total_pages", 0)))
        request = Request(
            url,
            headers={"User-Agent": "TY-Image-Spider/2.2", "Accept": "application/json"},
        )
        try:
            with self._open_url(request, timeout=30) as response:
                require_https_host(
                    response.geturl(),
                    lambda host: host == urlsplit(self._base).hostname,
                )
                data = json.loads(read_limited(response, 12 * 1024 * 1024))
                pages = int(response.headers.get("X-WP-TotalPages", 0))
            if not isinstance(data, (dict, list)):
                raise ValueError("invalid JSON root")
        except HTTPError as exc:
            suffix = (
                "请求过于频繁，请稍后重试"
                if exc.code == 429
                else "暂时无法访问，请稍后重试"
            )
            raise SpiderError(
                "source_unavailable", self._label + suffix, status=502
            ) from None
        except (OSError, HTTPException) as exc:
            raise SpiderError(
                "source_unavailable", self._label + "连接失败，请稍后重试", status=502
            ) from exc
        except (ValueError, UnicodeError) as exc:
            raise SpiderError(
                "source_invalid_response", self._label + "返回数据无效", status=502
            ) from exc
        if self._cache:
            self._cache.put(url, {"data": data, "total_pages": pages})
        return JsonResponse(data, pages)
