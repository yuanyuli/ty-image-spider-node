"""Wallhaven 公共 API 客户端。"""

from __future__ import annotations

from ..version import USER_AGENT
from ..network_retry import retry_delay as _retry_delay

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


_API_ROOT = "https://wallhaven.cc/api/v1"
_MAX_API_BYTES = 8 * 1024 * 1024
_SAFE_ID = re.compile(r"^[a-z0-9]{6}$")


@dataclass(frozen=True, slots=True)
class WallhavenPage:
    items: tuple[dict[str, Any], ...]
    current_page: int
    last_page: int


class WallhavenClient:
    def __init__(
        self,
        open_url: Callable[..., Any] = urlopen,
        *,
        sleep: Callable[[float], None] = time.sleep,
        timeout_seconds: int = 30,
        max_retries: int = 2,
    ) -> None:
        self._open_url = open_url
        self._sleep = sleep
        self._timeout_seconds = timeout_seconds
        self._max_retries = max(0, max_retries)

    def search(self, params: Mapping[str, object]) -> WallhavenPage:
        query = urlencode(
            [(key, value) for key, value in params.items() if value not in (None, "")]
        )
        payload = self._request_json(
            f"{_API_ROOT}/search?{query}" if query else f"{_API_ROOT}/search"
        )
        raw_items = payload.get("data")
        metadata = payload.get("meta")
        if not isinstance(raw_items, list) or not isinstance(metadata, Mapping):
            raise SpiderError(
                "wallhaven_invalid_response", "Wallhaven 返回的数据格式无效", status=502
            )
        current_page = _positive_int(metadata.get("current_page"), "current_page")
        last_page = _positive_int(metadata.get("last_page"), "last_page")
        items = tuple(dict(item) for item in raw_items if isinstance(item, Mapping))
        return WallhavenPage(items, current_page, last_page)

    def detail(self, item_id: str) -> dict[str, Any]:
        if not _SAFE_ID.fullmatch(item_id):
            raise SpiderError("invalid_asset", "Wallhaven 素材 ID 无效")
        payload = self._request_json(f"{_API_ROOT}/w/{item_id}")
        data = payload.get("data")
        if not isinstance(data, Mapping):
            raise SpiderError(
                "wallhaven_invalid_response", "Wallhaven 详情数据格式无效", status=502
            )
        return dict(data)

    def _request_json(self, url: str) -> dict[str, Any]:
        for attempt in range(self._max_retries + 1):
            request = Request(
                url,
                headers={
                    "Accept": "application/json",
                    "User-Agent": USER_AGENT,
                },
            )
            try:
                with self._open_url(request, timeout=self._timeout_seconds) as response:
                    require_https_host(
                        response.geturl(), lambda host: host == "wallhaven.cc"
                    )
                    payload = json.loads(
                        read_limited(response, _MAX_API_BYTES).decode("utf-8")
                    )
                    if not isinstance(payload, dict):
                        raise ValueError("root is not an object")
                    return payload
            except HTTPError as exc:
                if (
                    exc.code == 429 or 500 <= exc.code < 600
                ) and attempt < self._max_retries:
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
                    "wallhaven_invalid_response",
                    "Wallhaven 返回的数据无法解析",
                    status=502,
                ) from exc
        raise SpiderError("wallhaven_unavailable", "Wallhaven 暂时不可用", status=502)

    @staticmethod
    def _map_error(error: BaseException) -> SpiderError:
        if isinstance(error, HTTPError):
            if error.code == 429:
                return SpiderError(
                    "wallhaven_rate_limited",
                    "Wallhaven 请求过于频繁",
                    "请稍后重试",
                    429,
                )
            if error.code == 404:
                return SpiderError(
                    "wallhaven_not_found", "Wallhaven 素材不存在", status=404
                )
            return SpiderError(
                "wallhaven_http_error",
                f"Wallhaven 请求失败（{error.code}）",
                status=502,
            )
        if isinstance(error, (TimeoutError, socket.timeout)) or (
            isinstance(error, URLError)
            and isinstance(error.reason, (TimeoutError, socket.timeout))
        ):
            return SpiderError("wallhaven_timeout", "Wallhaven 请求超时", status=504)
        return SpiderError("wallhaven_unavailable", "无法连接 Wallhaven", status=502)


def _positive_int(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise SpiderError(
            "wallhaven_invalid_response",
            f"Wallhaven 分页字段 {field} 无效",
            status=502,
        )
    return value
