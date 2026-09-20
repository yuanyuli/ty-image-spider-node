import json
from io import BytesIO
from urllib.error import HTTPError

import pytest

from ty_image_spider.cache import JsonCache
from ty_image_spider.models import SpiderError
from ty_image_spider.providers.museum_client import MuseumClient


def test_museum_metadata_cache_separates_pages_and_refreshes(tmp_path):
    calls = []

    def read(request, timeout):
        calls.append(request.full_url)
        response = BytesIO(json.dumps({"number": len(calls)}).encode())
        response.geturl = lambda: request.full_url
        return response

    client = MuseumClient("vam", JsonCache(tmp_path), open_url=read)
    assert client.get("objects/search", {"page": 1})["number"] == 1
    assert client.get("objects/search", {"page": 1})["number"] == 1
    assert client.get("objects/search", {"page": 2})["number"] == 2
    assert client.get("objects/search", {"page": 1}, refresh=True)["number"] == 3


def test_museum_client_reports_rate_limit_and_invalid_json():
    def limited(request, timeout):
        raise HTTPError(request.full_url, 429, "limited", {}, None)

    with pytest.raises(SpiderError, match="频繁"):
        MuseumClient("artic", open_url=limited).get("artworks/search", {})
    response = BytesIO(b"<html>no</html>")
    response.geturl = lambda: "https://api.artic.edu/api/v1/artworks/search"
    with pytest.raises(SpiderError, match="数据"):
        MuseumClient("artic", open_url=lambda *a, **k: response).get(
            "artworks/search", {}
        )


def test_museum_client_refuses_foreign_redirect_before_reading():
    class Redirect:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def geturl(self):
            return "https://example.org/data"

        def read(self, *args):
            pytest.fail("不应读取跨域响应")

    with pytest.raises(SpiderError):
        MuseumClient("artic", open_url=lambda *a, **k: Redirect()).get(
            "artworks/search", {}
        )
