from io import BytesIO
import asyncio
from types import SimpleNamespace

import pytest
from PIL import Image
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from ty_image_spider.asset_index import AssetIndex
from ty_image_spider.models import AssetItem, SpiderError
from ty_image_spider.providers.curated_download import CuratedDownloader
from ty_image_spider.providers.editorial import EditorialProvider
from ty_image_spider.providers.editorial_sources import COLOSSAL
from ty_image_spider.providers.registry import ProviderRegistry
from ty_image_spider.services.download import DownloadService
from ty_image_spider.routes import ROUTES


def setup_gallery(tmp_path, monkeypatch, *, cached=False):
    provider = EditorialProvider(COLOSSAL, None)
    registry = ProviderRegistry()
    registry.register(provider)
    images = [
        "https://www.thisiscolossal.com/red.png",
        "https://www.thisiscolossal.com/blue.png",
    ]
    item = AssetItem(
        "colossal",
        "42",
        preview_url=images[0],
        download_mode="gallery",
        metadata={"images": images},
    )
    reads = []

    def read(self, url):
        reads.append(url)
        data = BytesIO()
        Image.new("RGB", (2, 2), "blue" if url.endswith("blue.png") else "red").save(
            data, "PNG"
        )
        return data.getvalue(), ".png"

    monkeypatch.setattr(CuratedDownloader, "read", read)
    index = AssetIndex(tmp_path) if cached else None
    if index:
        index.store(provider.detail(item), b"cached-preview", ".png")
        item = index.overlay(item)
    return DownloadService(registry, tmp_path / "ty-node", index), item, reads


@pytest.mark.parametrize("cached", [False, True])
def test_download_selected_gallery_image_writes_only_that_image(
    tmp_path, monkeypatch, cached
):
    service, item, reads = setup_gallery(tmp_path, monkeypatch, cached=cached)
    result = service.execute_image({"item": item.to_dict(), "image_index": 1})
    assert result.files == ("ty-image-spider/colossal/42-2.png",)
    assert result.output_root == str((tmp_path / "ty-node").resolve())
    assert reads == ["https://www.thisiscolossal.com/blue.png"]
    with Image.open(tmp_path / "ty-node" / result.files[0]) as image:
        assert image.getpixel((0, 0)) == (0, 0, 255)
    assert not (tmp_path / "ty-node/ty-image-spider/colossal/42-1.png").exists()


@pytest.mark.parametrize("index", [-1, 2, True, "1", 0.5, None])
def test_download_selected_rejects_invalid_index_before_writing(
    tmp_path, monkeypatch, index
):
    service, item, reads = setup_gallery(tmp_path, monkeypatch)
    with pytest.raises(SpiderError, match="图片序号"):
        service.execute_image({"item": item.to_dict(), "image_index": index})
    assert reads == []
    assert not (tmp_path / "ty-node").exists()


def test_selected_download_keeps_provider_host_validation(tmp_path, monkeypatch):
    service, item, reads = setup_gallery(tmp_path, monkeypatch)
    payload = item.to_dict()
    payload["metadata"]["images"][1] = "https://evil.example/private.png"
    with pytest.raises(SpiderError):
        service.execute_image({"item": payload, "image_index": 1})
    assert reads == []


def test_whole_gallery_download_still_saves_all_images(tmp_path, monkeypatch):
    service, item, reads = setup_gallery(tmp_path, monkeypatch)
    result = service.execute({"item": item.to_dict()})
    assert len(result.files) == 2
    assert len(reads) == 2


def test_selected_download_http_returns_path_and_rejects_bad_index(
    tmp_path, monkeypatch
):
    service, item, _ = setup_gallery(tmp_path, monkeypatch)

    async def scenario():
        app = web.Application()
        method, path, handler = next(
            route for route in ROUTES if route[1].endswith("/download-image")
        )

        async def route(request):
            return await handler(request, SimpleNamespace(download=service))

        app.router.add_route(method, path, route)
        async with TestClient(TestServer(app)) as client:
            response = await client.post(
                path, json={"item": item.to_dict(), "image_index": 1}
            )
            assert response.status == 200
            body = await response.json()
            assert body["data"]["files"] == ["ty-image-spider/colossal/42-2.png"]
            response = await client.post(
                path, json={"item": item.to_dict(), "image_index": 100}
            )
            assert response.status == 400
            assert (await response.json())["error"]["code"] == "invalid_image_index"

    asyncio.run(scenario())
