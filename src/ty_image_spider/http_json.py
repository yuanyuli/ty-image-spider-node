"""限制本节点 JSON 正文，独立于 ComfyUI 的全局 aiohttp 配置。"""

from __future__ import annotations

import json
from typing import Mapping

from aiohttp import web

from .models import SpiderError

MAX_JSON_BYTES = 1024 * 1024


def _invalid_constant(value: str) -> None:
    raise ValueError("JSON 不接受非有限数值")


def _check_depth(value: object, depth: int = 0) -> None:
    if depth > 64:
        raise ValueError("JSON 层级过深")
    if isinstance(value, dict):
        for child in value.values():
            _check_depth(child, depth + 1)
    elif isinstance(value, list):
        for child in value:
            _check_depth(child, depth + 1)


class JsonBodyReader:
    def __init__(self, max_bytes: int = MAX_JSON_BYTES, chunk_bytes: int = 65536):
        if max_bytes < 1 or chunk_bytes < 1:
            raise ValueError("正文限制必须为正数")
        self._max_bytes = max_bytes
        self._chunk_bytes = min(chunk_bytes, max_bytes + 1)

    async def read(self, request: web.Request) -> Mapping[str, object]:
        if (
            request.content_length is not None
            and request.content_length > self._max_bytes
        ):
            raise self._too_large()
        payload = bytearray()
        try:
            async for chunk in request.content.iter_chunked(self._chunk_bytes):
                if len(payload) + len(chunk) > self._max_bytes:
                    raise self._too_large()
                payload.extend(chunk)
        except web.HTTPRequestEntityTooLarge as exc:
            raise self._too_large() from exc
        try:
            value = json.loads(
                payload.decode("utf-8"), parse_constant=_invalid_constant
            )
            _check_depth(value)
        except (ValueError, RecursionError) as exc:
            raise SpiderError("invalid_json", "请求正文不是有效 JSON 对象") from exc
        if not isinstance(value, Mapping):
            raise SpiderError("invalid_json", "请求正文必须是 JSON 对象")
        return value

    def _too_large(self) -> SpiderError:
        return SpiderError(
            "request_too_large",
            f"请求正文不能超过 {self._max_bytes} 字节（默认 1 MiB）",
            status=413,
        )
