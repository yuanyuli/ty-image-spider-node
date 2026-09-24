"""Wikimedia Commons 视频来源契约测试。"""

from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from ty_image_spider.domain import DownloadResult, SearchRequest
from ty_image_spider.providers.videos.commons import (
    CommonsVideoClient,
    CommonsVideoProvider,
    normalize_detail,
)


FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
SEARCH = json.loads(
    (FIXTURES / "commons_video_search.json").read_text(encoding="utf-8")
)
DETAIL = json.loads(
    (FIXTURES / "commons_video_detail.json").read_text(encoding="utf-8")
)


class FakeClient:
    def __init__(self, detail=None):
        self.calls = []
        self._detail = detail or DETAIL

    def search(self, query, category, cursor, refresh=False):
        self.calls.append(("search", query, category, cursor, refresh))
        return SEARCH

    def detail(self, title, refresh=False):
        self.calls.append(("detail", title, refresh))
        return self._detail


class FakeDownloader:
    def __init__(self):
        self.calls = []

    def download(self, resource, item_id, output_root):
        self.calls.append((resource, item_id, output_root))
        return DownloadResult((f"ty-image-spider/commons-video/{item_id}.webm",))


def test_commons_video_client_constrains_file_namespace_and_video_type():
    requests = []

    class Response(BytesIO):
        def geturl(self):
            return "https://commons.wikimedia.org/w/api.php"

    def open_url(request, timeout):
        requests.append(request)
        return Response(json.dumps(SEARCH).encode())

    client = CommonsVideoClient(open_url=open_url)
    client.search("city", "film", None)

    params = parse_qs(urlsplit(requests[0].full_url).query)
    assert params["gsrnamespace"] == ["6"]
    assert params["gsrlimit"] == ["24"]
    assert "filetype:video" in params["gsrsearch"][0]
    assert "city" in params["gsrsearch"][0]
    assert params["prop"] == ["videoinfo"]
    assert "derivatives" in params["viprop"][0]


def test_commons_video_search_round_trips_cursor_and_metadata():
    client = FakeClient()
    provider = CommonsVideoProvider(client, FakeDownloader())

    page = provider.search(
        SearchRequest("commons-video", "city", {"category": "film"}, "s:12")
    )

    assert client.calls[0] == ("search", "city", "film", "s:12", False)
    assert page.next_cursor == "s:24"
    item = page.items[0]
    assert item.provider == "commons-video"
    assert item.kind == "video"
    assert item.id == "123456"
    assert item.duration_seconds == 96
    assert item.author == "Alice"
    assert item.metadata["rights"] == "CC BY-SA 4.0"
    assert item.metadata["attribution_required"] is True


def test_commons_video_detail_prefers_mp4_playback_and_original_download():
    item = CommonsVideoProvider(FakeClient(), FakeDownloader()).search(
        SearchRequest("commons-video")
    ).items[0]

    detail = normalize_detail(item, DETAIL)

    playback = next(resource for resource in detail.media if resource.role == "playback")
    download = next(resource for resource in detail.media if resource.role == "download")
    assert playback.mime_type == "video/mp4"
    assert playback.width == 1280
    assert download.url.endswith("Example_film.webm")
    assert download.size_bytes == 90000000
    assert detail.content == "A city film."
    assert detail.item.author == "Alice"
    assert all("attacker.test" not in resource.url for resource in detail.media)


def test_commons_video_missing_derivatives_keeps_original_download():
    payload = json.loads(json.dumps(DETAIL))
    payload["query"]["pages"][0]["videoinfo"][0]["derivatives"] = []
    provider = CommonsVideoProvider(FakeClient(payload), FakeDownloader())
    item = provider.search(SearchRequest("commons-video")).items[0]

    detail = provider.detail(item)

    assert [resource.role for resource in detail.media] == ["download"]
    assert detail.images == (item.preview_url,)


def test_commons_video_rejects_unsafe_original_upload_host():
    payload = json.loads(json.dumps(DETAIL))
    payload["query"]["pages"][0]["videoinfo"][0]["url"] = (
        "https://attacker.test/original.webm"
    )
    provider = CommonsVideoProvider(FakeClient(payload), FakeDownloader())
    item = provider.search(SearchRequest("commons-video")).items[0]

    detail = provider.detail(item)

    assert all(resource.role != "download" for resource in detail.media)


def test_commons_video_download_delegates_original_resource(tmp_path):
    downloader = FakeDownloader()
    provider = CommonsVideoProvider(FakeClient(), downloader)
    item = provider.search(SearchRequest("commons-video")).items[0]

    provider.download(item, tmp_path)

    resource, item_id, output_root = downloader.calls[0]
    assert resource.role == "download"
    assert resource.url.endswith("Example_film.webm")
    assert item_id == "123456"
    assert output_root == tmp_path
