"""NASA 视频来源契约测试。"""

from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from ty_image_spider.domain import DownloadResult, SearchRequest, SpiderError
from ty_image_spider.providers.videos.nasa import NasaVideoClient, NasaVideoProvider


FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
SEARCH = json.loads((FIXTURES / "nasa_video_search.json").read_text(encoding="utf-8"))
MANIFEST = json.loads(
    (FIXTURES / "nasa_video_manifest.json").read_text(encoding="utf-8")
)


class FakeClient:
    def __init__(self, manifest=None):
        self.calls = []
        self._manifest = MANIFEST if manifest is None else manifest

    def search(self, query, page, refresh=False):
        self.calls.append(("search", query, page, refresh))
        return SEARCH

    def manifest(self, url, refresh=False):
        self.calls.append(("manifest", url, refresh))
        return self._manifest


class FakeDownloader:
    def __init__(self):
        self.calls = []

    def download(self, resource, item_id, output_root):
        self.calls.append((resource, item_id, output_root))
        return DownloadResult((f"ty-image-spider/nasa-video/{item_id}.mp4",))


def test_nasa_video_client_requests_video_media_type():
    requests = []

    class Response(BytesIO):
        def geturl(self):
            return "https://images-api.nasa.gov/search"

    def open_url(request, timeout):
        requests.append(request)
        return Response(json.dumps(SEARCH).encode())

    NasaVideoClient(open_url=open_url).search("apollo moon", 2)

    params = parse_qs(urlsplit(requests[0].full_url).query)
    assert params == {
        "media_type": ["video"],
        "page": ["2"],
        "page_size": ["24"],
        "q": ["apollo moon"],
    }


def test_nasa_video_search_combines_category_query_and_page_cursor():
    client = FakeClient()
    provider = NasaVideoProvider(client, FakeDownloader())

    page = provider.search(
        SearchRequest("nasa-video", "night", {"category": "earth"}, "2")
    )

    assert client.calls[0] == ("search", "earth from space night", 2, False)
    assert page.next_cursor == "3"
    item = page.items[0]
    assert item.id == "NHQ_2020_0427_Earth"
    assert item.kind == "video"
    assert item.preview_url.endswith("~thumb.jpg")
    assert item.source_url.endswith("NHQ_2020_0427_Earth")
    assert item.author == "NASA"


def test_nasa_video_client_rejects_unsafe_manifest_host_without_network():
    opened = False

    def open_url(*args, **kwargs):
        nonlocal opened
        opened = True
        raise AssertionError

    client = NasaVideoClient(open_url=open_url)

    with pytest.raises(SpiderError) as error:
        client.manifest("https://attacker.test/collection.json")

    assert error.value.code == "unsafe_url"
    assert opened is False


def test_nasa_video_client_encodes_spaces_in_manifest_path():
    requests = []

    class Response(BytesIO):
        def geturl(self):
            return (
                "https://images-assets.nasa.gov/video/SLS-4091%20August/collection.json"
            )

    def open_url(request, timeout):
        requests.append(request)
        return Response(b"[]")

    client = NasaVideoClient(open_url=open_url)
    client.manifest(
        "https://images-assets.nasa.gov/video/SLS-4091 August/collection.json"
    )

    assert requests[0].full_url == (
        "https://images-assets.nasa.gov/video/SLS-4091%20August/collection.json"
    )


def test_nasa_video_detail_selects_medium_playback_and_original_download():
    provider = NasaVideoProvider(FakeClient(), FakeDownloader())
    item = provider.search(SearchRequest("nasa-video")).items[0]

    detail = provider.detail(item)

    playback = next(
        resource for resource in detail.media if resource.role == "playback"
    )
    download = next(
        resource for resource in detail.media if resource.role == "download"
    )
    assert playback.url.endswith("~medium.mp4")
    assert download.url.endswith("~orig.mp4")
    assert all("attacker.test" not in resource.url for resource in detail.media)
    assert detail.content == "Earth science mission overview."


def test_nasa_video_missing_manifest_keeps_cover_and_metadata():
    provider = NasaVideoProvider(FakeClient([]), FakeDownloader())
    item = provider.search(SearchRequest("nasa-video")).items[0]

    detail = provider.detail(item)

    assert detail.media == ()
    assert detail.images == (item.preview_url,)
    assert detail.metadata["rights"] == "使用条件见 NASA 来源页面"


def test_nasa_video_ignores_unsafe_asset_urls():
    manifest = ["https://attacker.test/video~orig.mp4"]
    provider = NasaVideoProvider(FakeClient(manifest), FakeDownloader())
    item = provider.search(SearchRequest("nasa-video")).items[0]

    assert provider.detail(item).media == ()


def test_nasa_video_upgrades_official_http_media_urls_to_https():
    manifest = [
        "http://images-assets.nasa.gov/video/demo/demo~medium.mp4",
        "http://images-assets.nasa.gov/video/demo/demo~orig.mp4",
        "http://attacker.test/video/demo~orig.mp4",
    ]
    provider = NasaVideoProvider(FakeClient(manifest), FakeDownloader())
    item = provider.search(SearchRequest("nasa-video")).items[0]

    detail = provider.detail(item)

    assert [resource.url for resource in detail.media] == [
        "https://images-assets.nasa.gov/video/demo/demo~medium.mp4",
        "https://images-assets.nasa.gov/video/demo/demo~orig.mp4",
    ]


def test_nasa_video_download_delegates_highest_resource(tmp_path):
    downloader = FakeDownloader()
    provider = NasaVideoProvider(FakeClient(), downloader)
    item = provider.search(SearchRequest("nasa-video")).items[0]

    provider.download(item, tmp_path)

    resource, item_id, output_root = downloader.calls[0]
    assert resource.role == "download"
    assert resource.url.endswith("~orig.mp4")
    assert item_id == item.id
    assert output_root == tmp_path
