"""Prelinger Archives 视频来源契约测试。"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from ty_image_spider.domain import DownloadResult, SearchRequest, SpiderError
from ty_image_spider.infrastructure.video import VideoDownloadPolicy
from ty_image_spider.providers.videos.prelinger import (
    PrelingerClient,
    PrelingerProvider,
    normalize_detail,
    normalize_search_item,
)
from ty_image_spider.providers.videos.prelinger import provider as prelinger_module


FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
SEARCH = json.loads((FIXTURES / "prelinger_search.json").read_text(encoding="utf-8"))
METADATA = json.loads(
    (FIXTURES / "prelinger_metadata.json").read_text(encoding="utf-8")
)


class FakeClient:
    def __init__(self, metadata=None):
        self.calls = []
        self._metadata = metadata or METADATA

    def search(self, query, page, sort, refresh=False):
        self.calls.append(("search", query, page, sort, refresh))
        return SEARCH

    def metadata(self, identifier, refresh=False):
        self.calls.append(("metadata", identifier, refresh))
        return self._metadata


class FakeDownloader:
    def __init__(self):
        self.calls = []

    def download(self, resource, item_id, output_root):
        self.calls.append((resource, item_id, output_root))
        return DownloadResult((f"ty-image-spider/prelinger/{item_id}.mp4",))


def test_prelinger_client_uses_fixed_endpoints_and_24_item_pages():
    calls = []

    class Response:
        headers = {}

        def __enter__(self):
            from io import BytesIO

            self._stream = BytesIO(json.dumps(SEARCH).encode())
            return self

        def __exit__(self, *args):
            return None

        def read(self, size=-1):
            return self._stream.read(size)

        def geturl(self):
            return calls[-1].full_url

    def open_url(request, timeout):
        calls.append(request)
        return Response()

    client = PrelingerClient(open_url=open_url)
    client.search("future", 2, "popular")

    params = parse_qs(urlsplit(calls[0].full_url).query)
    assert urlsplit(calls[0].full_url).path == "/advancedsearch.php"
    assert params["rows"] == ["24"]
    assert params["page"] == ["2"]
    assert "collection:prelinger" in params["q"][0]
    assert "mediatype:movies" in params["q"][0]


def test_prelinger_download_policy_accepts_only_archive_host_and_subdomains():
    policy = VideoDownloadPolicy(
        "prelinger",
        prelinger_module.is_archive_download_host,
        r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}",
    )

    policy.require_url("https://archive.org/download/item/item.mp4")
    policy.require_url("https://dn801204.us.archive.org/0/items/item/item.mp4")
    with pytest.raises(SpiderError):
        policy.require_url("https://evilarchive.org/item.mp4")


def test_prelinger_search_normalizes_video_and_numeric_pagination():
    client = FakeClient()
    provider = PrelingerProvider(client, FakeDownloader())

    page = provider.search(
        SearchRequest("prelinger", "future", {"sort": "popular"}, "1")
    )

    assert client.calls[0] == ("search", "future", 1, "popular", False)
    assert page.next_cursor == "2"
    item = page.items[0]
    assert item.kind == "video"
    assert item.id == "Design_for_Dreaming"
    assert item.preview_url == "https://archive.org/services/img/Design_for_Dreaming"
    assert item.source_url == "https://archive.org/details/Design_for_Dreaming"
    assert item.author == "General Motors"
    assert item.created_at == "1956"


def test_prelinger_detail_selects_medium_playback_and_best_download():
    item = normalize_search_item(SEARCH["response"]["docs"][0])
    assert item is not None

    detail = normalize_detail(item, METADATA)

    assert detail.item.duration_seconds == 558
    assert detail.metadata["rights"] == "Public Domain Mark 1.0"
    playback = next(
        resource for resource in detail.media if resource.role == "playback"
    )
    download = next(
        resource for resource in detail.media if resource.role == "download"
    )
    assert playback.url.endswith("Design_for_Dreaming_512kb.mp4")
    assert playback.width == 640
    assert download.url.endswith("Design_for_Dreaming.mp4")
    assert download.size_bytes == 73400320
    assert all("escape" not in resource.url for resource in detail.media)


def test_prelinger_keeps_detail_when_no_playable_derivative_exists():
    raw = {"metadata": METADATA["metadata"], "files": []}
    item = normalize_search_item(SEARCH["response"]["docs"][0])
    assert item is not None

    detail = normalize_detail(item, raw)

    assert detail.media == ()
    assert detail.images == (item.preview_url,)


def test_prelinger_descriptor_supports_cache_but_not_bulk_download():
    descriptor = PrelingerProvider(FakeClient(), FakeDownloader()).descriptor()

    assert descriptor.presentation.group_id == "videos"
    assert descriptor.capabilities.cache is True
    assert descriptor.capabilities.bulk_download is False
    assert "封面" in descriptor.presentation.cache_description


def test_prelinger_download_delegates_selected_download_resource(tmp_path):
    downloader = FakeDownloader()
    provider = PrelingerProvider(FakeClient(), downloader)
    item = provider.search(SearchRequest("prelinger")).items[0]

    result = provider.download(item, tmp_path)

    assert result.files[0].endswith(".mp4")
    resource, item_id, output_root = downloader.calls[0]
    assert resource.role == "download"
    assert item_id == item.id
    assert output_root == tmp_path
