"""HTTP 成功、错误与敏感信息脱敏响应。"""

from __future__ import annotations

import re
from typing import Mapping

from aiohttp import web

from ..domain import JsonValue, SpiderError


_SECRET_VALUE = re.compile(
    r"(?i)\b((?:[a-z0-9]+[_-])*(?:key|token|secret)|cookie|authorization)\b"
    r"\s*[:=]\s*(?:Bearer\s+)?[^\s,;&]+"
)
_BEARER_VALUE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")


def success(value: object) -> web.Response:
    data = value.to_dict() if hasattr(value, "to_dict") else value
    return web.json_response({"ok": True, "data": data})


def error(exception: SpiderError) -> web.Response:
    return web.json_response(
        {
            "ok": False,
            "error": {
                "code": exception.code,
                "message": safe_text(exception.message),
                "action": safe_text(exception.action),
                **(
                    {"details": safe_json(exception.details)}
                    if exception.details
                    else {}
                ),
            },
        },
        status=exception.status,
    )


def unexpected_error() -> web.Response:
    return web.json_response(
        {
            "ok": False,
            "error": {
                "code": "internal_error",
                "message": "服务器处理请求时发生错误",
                "action": "请查看 ComfyUI 日志",
            },
        },
        status=500,
    )


def safe_text(value: str) -> str:
    return _BEARER_VALUE.sub(
        "Bearer [已隐藏]",
        _SECRET_VALUE.sub(lambda match: f"{match.group(1)}=[已隐藏]", value),
    )


def safe_json(value: object) -> JsonValue:
    if isinstance(value, Mapping):
        return {
            str(key): "[已隐藏]"
            if any(
                part in str(key).lower()
                for part in ("key", "token", "secret", "cookie", "authorization")
            )
            else safe_json(nested)
            for key, nested in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [safe_json(nested) for nested in value]
    if isinstance(value, str):
        return safe_text(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return "[已隐藏]"
