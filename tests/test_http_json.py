import asyncio
import json
from types import SimpleNamespace

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from ty_image_spider import routes
from ty_image_spider.models import SearchPage

LIMIT = 1024 * 1024


class UseCase:
    def __init__(self):
        self.calls = []

    def execute(self, payload):
        self.calls.append(payload)
        return SearchPage()

    start = execute
    execute_image = execute

    def download_page(self, provider, items):
        self.calls.append((provider, items))
        return {}


async def client_and_use_case():
    use_case = UseCase()
    services = SimpleNamespace(
        search=use_case, detail=use_case, download=use_case, cache_job=use_case
    )
    app = web.Application(client_max_size=16 * LIMIT)
    for path, handler in (
        ("search", routes.post_search),
        ("detail", routes.post_detail),
        ("download", routes.post_download),
        ("download-image", routes.post_download_image),
        ("download-page", routes.post_download_page),
        ("cache", routes.post_cache_start),
    ):

        async def wrapped(request, handler=handler):
            return await handler(request, services)

        app.router.add_post("/" + path, wrapped)
    client = TestClient(TestServer(app))
    await client.start_server()
    return client, use_case


@pytest.mark.parametrize(
    "path", ["search", "detail", "download", "download-image", "download-page", "cache"]
)
@pytest.mark.parametrize("chunked", [False, True])
def test_all_json_routes_reject_oversize_without_invoking_use_case(path, chunked):
    async def scenario():
        client, use_case = await client_and_use_case()

        async def chunks():
            for _ in range(17):
                yield b"a" * 65536

        try:
            response = await client.post(
                "/" + path,
                data=chunks() if chunked else b"x" * (LIMIT + 1),
                headers={"Content-Type": "application/json"},
            )
            assert response.status == 413
            assert (await response.json())["error"]["code"] == "request_too_large"
            assert use_case.calls == []
        finally:
            await client.close()

    asyncio.run(scenario())


@pytest.mark.parametrize("size", [LIMIT - 1, LIMIT])
def test_exact_byte_limit_is_accepted(size):
    async def scenario():
        client, use_case = await client_and_use_case()
        try:
            raw = b'{"x":"' + b"a" * (size - 8) + b'"}'
            assert len(raw) == size
            response = await client.post("/search", data=raw)
            assert response.status == 200
            assert use_case.calls == [json.loads(raw)]
        finally:
            await client.close()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"[]",
        b"null",
        b"{",
        b"\xff",
        b'{"x": NaN}',
        b'{"x":' + b"[" * 2000 + b"0" + b"]" * 2000 + b"}",
    ],
)
def test_invalid_json_is_rejected_without_echo(raw):
    async def scenario():
        client, use_case = await client_and_use_case()
        try:
            response = await client.post("/search", data=raw)
            assert response.status == 400
            assert (await response.json())["error"]["code"] == "invalid_json"
            assert use_case.calls == []
        finally:
            await client.close()

    asyncio.run(scenario())
