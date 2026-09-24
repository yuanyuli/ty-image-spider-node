"""ComfyUI 路由表声明与幂等注册。"""

from __future__ import annotations

import importlib
from typing import Awaitable, Callable

from aiohttp import web

from .handlers import (
    get_cache_status,
    get_providers,
    post_cache_cancel,
    post_cache_start,
    post_detail,
    post_download,
    post_download_image,
    post_download_page,
    post_opencli_connect,
    post_provider_check,
    post_search,
)


ROUTES: tuple[
    tuple[str, str, Callable[[web.Request], Awaitable[web.Response]]], ...
] = (
    ("GET", "/ty-image-spider/providers", get_providers),
    ("POST", "/ty-image-spider/search", post_search),
    ("POST", "/ty-image-spider/detail", post_detail),
    ("POST", "/ty-image-spider/download", post_download),
    ("POST", "/ty-image-spider/download-image", post_download_image),
    ("POST", "/ty-image-spider/download-page", post_download_page),
    ("POST", "/ty-image-spider/providers/xiaohongshu/check", post_provider_check),
    ("POST", "/ty-image-spider/providers/xiaohongshu/connect", post_opencli_connect),
    ("POST", "/ty-image-spider/cache/start", post_cache_start),
    ("GET", "/ty-image-spider/cache/{job_id}", get_cache_status),
    ("POST", "/ty-image-spider/cache/{job_id}/cancel", post_cache_cancel),
)

_routes_registered = False


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
