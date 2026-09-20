import json
from io import BytesIO
from urllib.parse import parse_qs, urlsplit

import pytest

from ty_image_spider.models import DownloadResult, SearchRequest, SpiderError
from ty_image_spider.providers.loc import LocProvider
from ty_image_spider.providers.public_json_client import PublicJsonClient


class Response(BytesIO):
    headers = {}

    def __init__(self, data, url):
        super().__init__(json.dumps(data).encode())
        self.url = url

    def geturl(self):
        return self.url


def client(payload, calls):
    def read(request, timeout):
        calls.append(request.full_url)
        return Response(payload, request.full_url)

    return PublicJsonClient("https://www.loc.gov/", "美国国会图书馆", open_url=read)


def record(item_id="2017857473"):
    root = "https://tile.loc.gov/storage-services/service/pnp/fsa/8d30800/"
    return {
        "id": f"http://www.loc.gov/item/{item_id}/",
        "url": f"https://www.loc.gov/item/{item_id}/",
        "title": "Workers beside a poster",
        "date": "1943-01-01",
        "description": ["Documentary photograph."],
        "image_url": [
            root + "photo_150px.jpg#h=150&w=150",
            root + "photo.gif#h=150&w=150",
            root + "photo_r.jpg#h=640&w=638",
            root + "photo_v.jpg#h=1024&w=1021",
        ],
        "item": {
            "id": item_id,
            "contributors": ["Collins, Marjory, photographer."],
            "medium_brief": "1 negative",
            "rights_information": "No known restrictions.",
        },
        "subject": ["documentary photographs", "workers"],
    }


def test_loc_uses_official_facets_pagination_and_largest_safe_image():
    calls = []
    payload = {
        "pagination": {"current": 2, "of": 50, "perpage": 24, "next": "page-3"},
        "results": [record(), {"id": "http://www.loc.gov/item/no-image/"}],
    }
    provider = LocProvider(client(payload, calls))

    page = provider.search(
        SearchRequest("loc", "workers", {"category": "documentary"}, cursor="2")
    )

    query = parse_qs(urlsplit(calls[0]).query)
    assert query["fo"] == ["json"] and query["c"] == ["24"]
    assert query["sp"] == ["2"] and query["q"] == ["workers"]
    assert "farm security administration" in query["fa"][0]
    assert page.next_cursor == "3" and len(page.items) == 1
    item = page.items[0]
    assert item.id == "2017857473" and item.author.startswith("Collins")
    assert item.preview_url.endswith("photo_r.jpg#h=640&w=638")
    detail = provider.detail(item)
    assert detail.images[0].endswith("photo_v.jpg#h=1024&w=1021")
    assert detail.content == "Documentary photograph."
    assert item.metadata["rights"] == "No known restrictions."


def test_loc_download_supports_safe_alphanumeric_ids(tmp_path):
    class Downloader:
        def download(self, url, provider, item_id, output):
            assert provider == "loc" and item_id == "afc1937002_001"
            assert url.startswith("https://tile.loc.gov/")
            return DownloadResult(("ty-image-spider/loc/afc1937002_001.jpg",))

    provider = LocProvider(client({}, []), Downloader())
    item = provider._item(record("afc1937002_001"))
    assert item is not None
    assert provider.download(item, tmp_path).files[0].endswith("afc1937002_001.jpg")


@pytest.mark.parametrize("cursor,category", [("../2", "documentary"), (None, "bad")])
def test_loc_rejects_invalid_filters_before_network(cursor, category):
    def unexpected(*args, **kwargs):
        pytest.fail("无效输入不应访问网络")

    provider = LocProvider(
        PublicJsonClient("https://www.loc.gov/", "美国国会图书馆", open_url=unexpected)
    )
    with pytest.raises(SpiderError):
        provider.search(
            SearchRequest("loc", filters={"category": category}, cursor=cursor)
        )
