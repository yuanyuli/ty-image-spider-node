"""TY Image Spider 的 11 个 aiohttp 请求处理器。"""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, Mapping

from aiohttp import web

from ..app import ApplicationServices
from ..domain import SpiderError
from ..infrastructure.diagnostics import log_failure
from .json_body import JsonBodyReader
from .responses import error, success, unexpected_error
from .service_locator import get_services


_LOGGER = logging.getLogger(__name__)
_body_reader = JsonBodyReader()


async def get_providers(
    request: web.Request, services: ApplicationServices | None = None
) -> web.Response:
    del request
    app = services or get_services()
    return await respond(lambda: app.status.list())


async def post_search(
    request: web.Request, services: ApplicationServices | None = None
) -> web.Response:
    app = services or get_services()
    return await execute_payload(request, app.search.execute)


async def post_detail(
    request: web.Request, services: ApplicationServices | None = None
) -> web.Response:
    app = services or get_services()
    return await execute_payload(request, app.detail.execute)


async def post_download(
    request: web.Request, services: ApplicationServices | None = None
) -> web.Response:
    app = services or get_services()
    return await execute_payload(request, app.download.execute)


async def post_download_image(
    request: web.Request, services: ApplicationServices | None = None
) -> web.Response:
    app = services or get_services()
    return await execute_payload(request, app.download.execute_image)


async def post_download_page(
    request: web.Request, services: ApplicationServices | None = None
) -> web.Response:
    app = services or get_services()
    try:
        payload = await request_json(request)
        provider = payload.get("provider")
        items = payload.get("items")
        if not isinstance(provider, str) or not provider:
            raise SpiderError("invalid_provider", "请求缺少有效的素材源")
        if not isinstance(items, list):
            raise SpiderError("invalid_items", "整页下载素材必须是数组")
        result = await asyncio.to_thread(app.download.download_page, provider, items)
        return success(result)
    except SpiderError as exc:
        return error(exc)
    except Exception as exc:
        log_failure(_LOGGER, "整页下载路由执行失败", exc)
        return unexpected_error()


async def post_provider_check(
    request: web.Request, services: ApplicationServices | None = None
) -> web.Response:
    del request
    app = services or get_services()
    return await respond(lambda: app.status.check("xiaohongshu"))


async def post_opencli_connect(
    request: web.Request, services: ApplicationServices | None = None
) -> web.Response:
    del request
    app = services or get_services()
    return await respond(app.opencli_connect.execute)


async def post_cache_start(
    request: web.Request, services: ApplicationServices | None = None
) -> web.Response:
    app = services or get_services()
    return await execute_payload(request, app.cache_job.start)


async def get_cache_status(
    request: web.Request, services: ApplicationServices | None = None
) -> web.Response:
    app = services or get_services()
    return await respond(lambda: app.cache_job.status(request.match_info["job_id"]))


async def post_cache_cancel(
    request: web.Request, services: ApplicationServices | None = None
) -> web.Response:
    app = services or get_services()
    return await respond(lambda: app.cache_job.cancel(request.match_info["job_id"]))


async def execute_payload(
    request: web.Request, execute: Callable[[Mapping[str, object]], object]
) -> web.Response:
    try:
        payload = await request_json(request)
        result = await asyncio.to_thread(execute, payload)
        return success(result)
    except SpiderError as exc:
        return error(exc)
    except Exception as exc:
        log_failure(_LOGGER, "图片素材路由执行失败", exc)
        return unexpected_error()


async def request_json(request: web.Request) -> Mapping[str, object]:
    return await _body_reader.read(request)


async def respond(call: Callable[[], object]) -> web.Response:
    try:
        result = await asyncio.to_thread(call)
        return success(result)
    except SpiderError as exc:
        return error(exc)
    except Exception as exc:
        log_failure(_LOGGER, "图片素材状态路由执行失败", exc)
        return unexpected_error()
