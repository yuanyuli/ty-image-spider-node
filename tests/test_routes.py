import asyncio
import json
import sys
from types import SimpleNamespace

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from ty_image_spider.models import (
    AssetDetail,
    AssetItem,
    DownloadResult,
    ProviderStatus,
    SearchPage,
    SpiderError,
)
from ty_image_spider import routes


def test_error_details_preserve_job_id_and_redact_nested_credentials():
    details = {
        "job_id": "safe",
        "nested": [{"access_token": "secret", "note": "cookie=secret"}],
    }
    response = routes._error(
        SpiderError("cache_duplicate", "重复", status=409, details=details)
    )
    payload = json.loads(response.body)
    assert payload["error"]["details"]["job_id"] == "safe"
    assert "secret" not in response.text
    assert details["nested"][0]["access_token"] == "secret"


from ty_image_spider.routes import (
    get_providers,
    post_detail,
    post_download,
    post_download_page,
    post_provider_check,
    post_search,
)


class FakeUseCase:
    def __init__(self, result):
        self.result = result
        self.error = None
        self.calls = []

    def execute(self, payload):
        self.calls.append(payload)
        if self.error:
            raise self.error
        return self.result


class FakeDownload(FakeUseCase):
    def download_page(self, provider, items):
        self.calls.append((provider, items))
        if self.error:
            raise self.error
        return self.result


class FakeStatus:
    def list(self):
        return ({"provider": {"id": "local"}, "status": {"available": True}},)

    def check(self, provider_id):
        return ProviderStatus(provider_id == "xiaohongshu", message="checked")


def fake_services():
    item = AssetItem("local", "1")
    return SimpleNamespace(
        search=FakeUseCase(SearchPage((item,))),
        detail=FakeUseCase(AssetDetail(item)),
        download=FakeDownload(DownloadResult(("a.png",), "已下载")),
        status=FakeStatus(),
    )


async def make_client(services):
    app = web.Application()

    def bind(handler):
        async def wrapped(request):
            return await handler(request, services)

        return wrapped

    app.router.add_get("/providers", bind(get_providers))
    app.router.add_post("/search", bind(post_search))
    app.router.add_post("/detail", bind(post_detail))
    app.router.add_post("/download", bind(post_download))
    app.router.add_post("/download-page", bind(post_download_page))
    app.router.add_post("/check", bind(post_provider_check))
    client = TestClient(TestServer(app))
    await client.start_server()
    return client


def test_search_route_returns_uniform_envelope():
    asyncio.run(_assert_search_route_returns_uniform_envelope())


async def _assert_search_route_returns_uniform_envelope():
    services = fake_services()
    client = await make_client(services)
    try:
        response = await client.post("/search", json={"provider": "local"})
        assert response.status == 200
        assert await response.json() == {
            "ok": True,
            "data": services.search.result.to_dict(),
        }
    finally:
        await client.close()


def test_route_maps_spider_error_without_secret():
    asyncio.run(_assert_route_maps_spider_error_without_secret())


async def _assert_route_maps_spider_error_without_secret():
    services = fake_services()
    services.search.error = SpiderError(
        "opencli_auth_required", "cookie=secret", "请重新登录", 401
    )
    client = await make_client(services)
    try:
        response = await client.post("/search", json={"provider": "xiaohongshu"})
        body = await response.json()
        assert response.status == 401
        assert body["error"]["code"] == "opencli_auth_required"
        assert "secret" not in json.dumps(body)
    finally:
        await client.close()


def test_routes_cover_malformed_json_status_and_download_page():
    asyncio.run(_assert_routes_cover_malformed_json_status_and_download_page())


async def _assert_routes_cover_malformed_json_status_and_download_page():
    services = fake_services()
    client = await make_client(services)
    try:
        malformed = await client.post(
            "/search", data="{", headers={"Content-Type": "application/json"}
        )
        assert malformed.status == 400
        assert (await malformed.json())["error"]["code"] == "invalid_json"

        providers = await client.get("/providers")
        assert (await providers.json())["data"][0]["provider"]["id"] == "local"

        checked = await client.post("/check", json={})
        assert (await checked.json())["data"]["available"] is True

        downloaded = await client.post(
            "/download-page", json={"provider": "local", "items": []}
        )
        assert downloaded.status == 200
        assert services.download.calls[-1] == ("local", [])
    finally:
        await client.close()


def test_register_routes_is_idempotent_and_safe_without_comfyui(monkeypatch):
    monkeypatch.setattr(routes, "_routes_registered", False)
    monkeypatch.delitem(sys.modules, "server", raising=False)
    assert routes.register_routes() is False

    table = web.RouteTableDef()
    monkeypatch.setitem(
        sys.modules,
        "server",
        SimpleNamespace(
            PromptServer=SimpleNamespace(instance=SimpleNamespace(routes=table))
        ),
    )
    assert routes.register_routes() is True
    count = len(table)
    assert routes.register_routes() is True
    assert len(table) == count == 10
