import json
from io import BytesIO
from urllib.parse import parse_qs, urlsplit

import pytest

from ty_image_spider.domain import DownloadResult, SearchRequest, SpiderError
from ty_image_spider.providers.collections.commons import (
    CommonsClient,
    CommonsPage,
    CommonsProvider,
)
from ty_image_spider.providers.collections.commons.normalizer import normalize_file


ROW = {
    "pageid": 89274662,
    "title": "File:Everything is Going to be Alright.jpg",
    "imageinfo": [
        {
            "width": 4342,
            "height": 1995,
            "url": "https://upload.wikimedia.org/wikipedia/commons/2/21/artwork.jpg",
            "thumburl": "https://thumb.wikimedia.org/wikipedia/commons/thumb/2/21/artwork.jpg/800px-artwork.jpg",
            "descriptionurl": "https://commons.wikimedia.org/wiki/File:Everything.jpg",
            "extmetadata": {
                "ObjectName": {"value": "Everything is Going to be Alright"},
                "Artist": {"value": "<a>Michal Klajban</a>"},
                "LicenseShortName": {"value": "CC BY-SA 4.0"},
                "UsageTerms": {"value": "Creative Commons Attribution-Share Alike 4.0"},
                "AttributionRequired": {"value": "true"},
            },
        }
    ],
}


class FakeClient:
    def __init__(self):
        self.calls = []

    def search(self, query, category, cursor):
        self.calls.append((query, category, cursor))
        return CommonsPage((ROW,), "continue-token")

    def file(self, page_id):
        return ROW


class FakeDownloader:
    def __init__(self):
        self.calls = []

    def download(self, url, item_id, output_root):
        self.calls.append((url, item_id, output_root))
        return DownloadResult((f"ty-image-spider/commons/{item_id}.jpg",))


def make_provider(client=None, downloader=None):
    return CommonsProvider(client or FakeClient(), downloader or FakeDownloader())


def test_commons_normalizes_featured_image_license_and_pagination():
    client = FakeClient()
    page = make_provider(client).search(
        SearchRequest("commons", "architecture", {"category": "featured"})
    )

    assert client.calls == [("architecture", "featured", None)]
    assert page.next_cursor == "continue-token"
    item = page.items[0]
    assert item.id == "89274662"
    assert item.author == "Michal Klajban"
    assert item.metadata["rights"] == "CC BY-SA 4.0"
    assert item.metadata["attribution_required"] is True


def test_commons_normalizer_preserves_license_and_original_image():
    item = normalize_file(ROW)

    assert item is not None
    assert item.id == "89274662"
    assert item.author == "Michal Klajban"
    assert item.metadata["rights"] == "CC BY-SA 4.0"
    assert item.metadata["original_url"].endswith("/artwork.jpg")


def test_commons_detail_reverifies_file_and_downloads_original(tmp_path):
    downloader = FakeDownloader()
    provider = make_provider(downloader=downloader)
    item = provider.search(SearchRequest("commons")).items[0]

    detail = provider.detail(item)
    assert detail.images == (
        "https://upload.wikimedia.org/wikipedia/commons/2/21/artwork.jpg",
    )
    provider.download(item, tmp_path)
    assert downloader.calls[0][0] == detail.images[0]


def test_commons_descriptor_uses_collection_group():
    descriptor = make_provider().descriptor()
    assert descriptor.presentation.group_id == "collections"
    assert descriptor.capabilities.cache is True


def test_commons_download_policy_rejects_thumbnail_host():
    with pytest.raises(SpiderError, match="图片地址不属于当前素材源"):
        CommonsProvider.image_policy.validate_url(
            "https://thumb.wikimedia.org/wikipedia/commons/thumb/a/a1/image.jpg"
        )


def test_commons_client_uses_categories_with_direct_image_members():
    requested_categories = []

    class Response(BytesIO):
        def geturl(self):
            return "https://commons.wikimedia.org/w/api.php"

    def open_url(request, timeout):
        params = parse_qs(urlsplit(request.full_url).query)
        requested_categories.append(params["gcmtitle"][0])
        payload = {"query": {"pages": []}}
        return Response(json.dumps(payload).encode())

    client = CommonsClient(open_url=open_url)
    client.search("", "photography", None)
    client.search("", "art", None)

    assert requested_categories == [
        "Category:Featured photographs in the public domain",
        "Category:Quality images of works of art",
    ]
