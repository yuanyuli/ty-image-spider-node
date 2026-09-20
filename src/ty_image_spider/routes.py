"""ComfyUI HTTP 路由适配。"""

from __future__ import annotations

import asyncio
import importlib
import logging
import re
import threading
from pathlib import Path
from typing import Awaitable, Callable, Mapping

from aiohttp import web

from .bootstrap import ApplicationServices, build_services
from .models import SpiderError


_LOGGER = logging.getLogger(__name__)
_SECRET_VALUE = re.compile(
    r"(?i)\b(key|token|secret|cookie|authorization)\b\s*[:=]\s*[^\s,;]+"
)
_routes_registered = False
_services: ApplicationServices | None = None
_services_lock = threading.Lock()


def get_services() -> ApplicationServices:
    global _services
    if _services is not None:
        return _services
    with _services_lock:
        if _services is None:
            folder_paths = importlib.import_module("folder_paths")
            output_root = Path(folder_paths.get_output_directory())
            cache_root = output_root / "ty-image-spider" / ".cache"
            _services = build_services(output_root, cache_root)
    return _services


async def get_providers(
    request: web.Request, services: ApplicationServices | None = None
) -> web.Response:
    del request
    app = services or get_services()
    return await _respond(lambda: app.status.list())


async def post_search(
    request: web.Request, services: ApplicationServices | None = None
) -> web.Response:
    app = services or get_services()
    return await _execute_payload(request, app.search.execute)


async def post_detail(
    request: web.Request, services: ApplicationServices | None = None
) -> web.Response:
    app = services or get_services()
    return await _execute_payload(request, app.detail.execute)


async def post_download(
    request: web.Request, services: ApplicationServices | None = None
) -> web.Response:
    app = services or get_services()
    return await _execute_payload(request, app.download.execute)


async def post_download_page(
    request: web.Request, services: ApplicationServices | None = None
) -> web.Response:
    app = services or get_services()
    try:
        payload = await _request_json(request)
        provider = payload.get("provider")
        items = payload.get("items")
        if not isinstance(provider, str) or not provider:
            raise SpiderError("invalid_provider", "请求缺少有效的素材源")
        if not isinstance(items, list):
            raise SpiderError("invalid_items", "整页下载素材必须是数组")
        result = await asyncio.to_thread(app.download.download_page, provider, items)
        return _success(result)
    except SpiderError as exc:
        return _error(exc)
    except Exception:
        _LOGGER.exception("整页下载路由执行失败")
        return _unexpected_error()


async def post_provider_check(
    request: web.Request, services: ApplicationServices | None = None
) -> web.Response:
    del request
    app = services or get_services()
    return await _respond(lambda: app.status.check("xiaohongshu"))


async def post_opencli_connect(
    request: web.Request, services: ApplicationServices | None = None
) -> web.Response:
    del request
    app = services or get_services()
    return await _respond(app.opencli_connect.execute)


async def post_cache_start(
    request: web.Request, services: ApplicationServices | None = None
) -> web.Response:
    app = services or get_services()
    return await _execute_payload(request, app.cache_job.start)


async def get_cache_status(
    request: web.Request, services: ApplicationServices | None = None
) -> web.Response:
    app = services or get_services()
    return await _respond(lambda: app.cache_job.status(request.match_info["job_id"]))


async def post_cache_cancel(
    request: web.Request, services: ApplicationServices | None = None
) -> web.Response:
    app = services or get_services()
    return await _respond(lambda: app.cache_job.cancel(request.match_info["job_id"]))


async def _execute_payload(
    request: web.Request, execute: Callable[[Mapping[str, object]], object]
) -> web.Response:
    try:
        payload = await _request_json(request)
        result = await asyncio.to_thread(execute, payload)
        return _success(result)
    except SpiderError as exc:
        return _error(exc)
    except Exception:
        _LOGGER.exception("图片素材路由执行失败")
        return _unexpected_error()


async def _request_json(request: web.Request) -> Mapping[str, object]:
    try:
        payload = await request.json()
    except Exception as exc:
        raise SpiderError("invalid_json", "请求正文不是有效 JSON") from exc
    if not isinstance(payload, Mapping):
        raise SpiderError("invalid_json", "请求正文必须是 JSON 对象")
    return payload


async def _respond(call: Callable[[], object]) -> web.Response:
    try:
        result = await asyncio.to_thread(call)
        return _success(result)
    except SpiderError as exc:
        return _error(exc)
    except Exception:
        _LOGGER.exception("图片素材状态路由执行失败")
        return _unexpected_error()


def _success(value: object) -> web.Response:
    data = value.to_dict() if hasattr(value, "to_dict") else value
    return web.json_response({"ok": True, "data": data})


def _error(error: SpiderError) -> web.Response:
    return web.json_response(
        {
            "ok": False,
            "error": {
                "code": error.code,
                "message": _safe_text(error.message),
                "action": _safe_text(error.action),
            },
        },
        status=error.status,
    )


def _unexpected_error() -> web.Response:
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


def _safe_text(value: str) -> str:
    return _SECRET_VALUE.sub(lambda match: f"{match.group(1)}=[已隐藏]", value)


ROUTES: tuple[
    tuple[str, str, Callable[[web.Request], Awaitable[web.Response]]], ...
] = (
    ("GET", "/ty-image-spider/providers", get_providers),
    ("POST", "/ty-image-spider/search", post_search),
    ("POST", "/ty-image-spider/detail", post_detail),
    ("POST", "/ty-image-spider/download", post_download),
    ("POST", "/ty-image-spider/download-page", post_download_page),
    ("POST", "/ty-image-spider/providers/xiaohongshu/check", post_provider_check),
    ("POST", "/ty-image-spider/providers/xiaohongshu/connect", post_opencli_connect),
    ("POST", "/ty-image-spider/cache/start", post_cache_start),
    ("GET", "/ty-image-spider/cache/{job_id}", get_cache_status),
    ("POST", "/ty-image-spider/cache/{job_id}/cancel", post_cache_cancel),
)


def register_routes() -> bool:
    global _routes_registered
    if _routes_registered:
        return True
    try:
        server_module = importlib.import_module("server")
    except ImportError:
        return False
    server = getattr(getattr(server_module, "PromptServer", None), "instance", None)
    table = getattr(server, "routes", None)
    if table is None:
        return False
    for method, path, handler in ROUTES:
        registrar = table.get if method == "GET" else table.post
        registrar(path)(handler)
    _routes_registered = True
    return True
