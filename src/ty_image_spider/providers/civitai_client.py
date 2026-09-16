"""Civitai HTTP 访问与错误映射。"""

from __future__ import annotations

import json
import re
import socket
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ..models import SpiderError
from ..security import read_limited, require_https_host


_ALLOWED_SITES = frozenset({"civitai.com", "civitai.red"})
_MAX_API_BYTES = 8 * 1024 * 1024
_MAX_PAGE_BYTES = 12 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class CivitaiPage:
    items: tuple[dict[str, Any], ...]
    next_cursor: str | None = None


class CivitaiClient:
    def __init__(
        self,
        open_url: Callable[..., Any] = urlopen,
        *,
        api_key: str = "",
        sleep: Callable[[float], None] = time.sleep,
        timeout_seconds: int = 30,
        max_retries: int = 2,
    ) -> None:
        self._open_url = open_url
        self._api_key = api_key.strip()
        self._sleep = sleep
        self._timeout_seconds = timeout_seconds
        self._max_retries = max(0, max_retries)

    def search(self, site: str, params: Mapping[str, object]) -> CivitaiPage:
        self._require_site(site)
        query = urlencode(
            [(key, value) for key, value in params.items() if value is not None and value != ""]
        )
        url = f"https://{site}/api/v1/images"
        if query:
            url = f"{url}?{query}"
        payload = self._request_json(url)
        raw_items = payload.get("items", [])
        metadata = payload.get("metadata", {})
        if not isinstance(raw_items, list) or not isinstance(metadata, Mapping):
            raise SpiderError("civitai_invalid_response", "Civitai 返回的数据格式无效", status=502)
        items = tuple(dict(item) for item in raw_items if isinstance(item, Mapping))
        cursor = metadata.get("nextCursor")
        return CivitaiPage(items, str(cursor) if cursor not in (None, "") else None)

    def page_metadata(self, site: str, image_id: str) -> dict[str, Any]:
        self._require_site(site)
        if not image_id.isdigit():
            raise SpiderError("invalid_asset", "Civitai 素材 ID 无效")
        request = self._request(f"https://{site}/images/{image_id}", accept="text/html")
        try:
            with self._open_url(request, timeout=self._timeout_seconds) as response:
                self._validate_final_url(response.geturl(), site)
                html = read_limited(response, _MAX_PAGE_BYTES).decode("utf-8", errors="replace")
        except (HTTPError, URLError, TimeoutError, socket.timeout) as exc:
            raise self._map_error(exc) from exc
        return _extract_page_metadata(html)

    def _request_json(self, url: str) -> dict[str, Any]:
        for attempt in range(self._max_retries + 1):
            request = self._request(url, accept="application/json")
            try:
                with self._open_url(request, timeout=self._timeout_seconds) as response:
                    parsed = require_https_host(
                        response.geturl(), lambda host: host in _ALLOWED_SITES
                    )
                    if parsed.hostname not in _ALLOWED_SITES:
                        raise SpiderError("unsafe_redirect", "Civitai 请求发生了不安全的重定向")
                    payload = json.loads(read_limited(response, _MAX_API_BYTES).decode("utf-8"))
                    if not isinstance(payload, dict):
                        raise ValueError("root is not an object")
                    return payload
            except HTTPError as exc:
                if exc.code == 429 or 500 <= exc.code < 600:
                    if attempt < self._max_retries:
                        self._sleep(_retry_delay(exc, attempt))
                        continue
                raise self._map_error(exc) from exc
            except (URLError, TimeoutError, socket.timeout) as exc:
                if attempt < self._max_retries:
                    self._sleep(float(attempt + 1))
                    continue
                raise self._map_error(exc) from exc
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                raise SpiderError(
                    "civitai_invalid_response", "Civitai 返回的数据无法解析", status=502
                ) from exc
        raise SpiderError("civitai_unavailable", "Civitai 暂时不可用", status=502)

    def _request(self, url: str, *, accept: str) -> Request:
        headers = {"Accept": accept, "User-Agent": "TY-Image-Spider/2.0"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return Request(url, headers=headers)

    @staticmethod
    def _require_site(site: str) -> None:
        if site not in _ALLOWED_SITES:
            raise SpiderError("civitai_invalid_site", "不支持的 Civitai 站点")

    @staticmethod
    def _validate_final_url(url: str, site: str) -> None:
        parsed = require_https_host(url, lambda host: host == site)
        if parsed.hostname != site:
            raise SpiderError("unsafe_redirect", "Civitai 请求发生了不安全的重定向")

    @staticmethod
    def _map_error(error: BaseException) -> SpiderError:
        if isinstance(error, HTTPError):
            if error.code == 403:
                return SpiderError(
                    "civitai_forbidden",
                    "Civitai 拒绝了当前请求",
                    "请检查 API Key 或稍后重试",
                    403,
                )
            if error.code == 429:
                return SpiderError(
                    "civitai_rate_limited", "Civitai 请求过于频繁", "请稍后重试", 429
                )
            return SpiderError(
                "civitai_http_error", f"Civitai 请求失败（{error.code}）", status=502
            )
        if isinstance(error, (TimeoutError, socket.timeout)):
            return SpiderError("civitai_timeout", "Civitai 请求超时", status=504)
        if isinstance(error, URLError) and isinstance(error.reason, (TimeoutError, socket.timeout)):
            return SpiderError("civitai_timeout", "Civitai 请求超时", status=504)
        return SpiderError("civitai_unavailable", "无法连接 Civitai", status=502)


def _retry_delay(error: HTTPError, attempt: int) -> float:
    raw = error.headers.get("Retry-After") if error.headers else None
    try:
        return max(0.0, min(float(raw), 30.0)) if raw is not None else float(attempt + 1)
    except (TypeError, ValueError):
        return float(attempt + 1)


def _extract_page_metadata(html: str) -> dict[str, Any]:
    """从页面脚本中提取最接近图片详情的 JSON 对象。"""

    for match in re.finditer(r'<script[^>]*type=["\']application/json["\'][^>]*>(.*?)</script>', html, re.I | re.S):
        try:
            value = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        found = _find_metadata(value)
        if found:
            return found
    return {}


def _find_metadata(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        if any(key in value for key in ("prompt", "negativePrompt", "workflow")):
            return dict(value)
        for child in value.values():
            found = _find_metadata(child)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _find_metadata(child)
            if found:
                return found
    return {}
