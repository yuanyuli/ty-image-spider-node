from pathlib import Path

from ty_image_spider.infrastructure.cache import JsonCache
from ty_image_spider.domain import DownloadResult, SearchRequest, SpiderError
from ty_image_spider.providers.wallpapers.netbian import (
    NetbianListPage,
    NetbianProvider,
)


FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


class FakeClient:
    def __init__(self, error=None):
        self.error = error
        self.list_calls = []
        self.detail_calls = []

    def list(self, path, page):
        self.list_calls.append((path, page))
        if self.error:
            raise self.error
        return NetbianListPage(
            FIXTURES.joinpath("netbian_list.html").read_text(encoding="utf-8"),
            page,
            2,
        )

    def detail(self, item_id):
        self.detail_calls.append(item_id)
        return FIXTURES.joinpath("netbian_detail.html").read_text(encoding="utf-8")


class FakeDownloader:
    def __init__(self):
        self.calls = []

    def download(self, url, item_id, output_root):
        self.calls.append((url, item_id, output_root))
        return DownloadResult((f"ty-image-spider/netbian/{item_id}.jpg",), "已下载")


def make_provider(tmp_path, client=None, downloader=None):
    return NetbianProvider(
        client or FakeClient(), JsonCache(tmp_path), downloader or FakeDownloader()
    )


def test_netbian_descriptor_and_categories(tmp_path):
    descriptor = make_provider(tmp_path).descriptor()

    assert descriptor.id == "netbian"
    assert descriptor.presentation.group_id == "wallpaper"
    assert descriptor.capabilities.pagination == "page"
    assert {field.name for field in descriptor.filters} == {"category"}


def test_netbian_search_maps_category_and_parses_items(tmp_path):
    client = FakeClient()
    page = make_provider(tmp_path, client).search(
        SearchRequest("netbian", filters={"category": "landscape"})
    )

    assert client.list_calls == [("/4kfengjing/", 1)]
    assert page.next_cursor == "2"
    assert page.items[0].id == "44070"
    assert page.items[0].preview_url.endswith("151348-1789974828a29a.jpg")
    assert page.items[0].source_url == "https://pic.netbian.com/tupian/44070.html"
    assert page.items[0].title == "秋日白桦落叶风景4K高清"


def test_netbian_detail_extracts_original_and_resolution(tmp_path):
    client = FakeClient()
    provider = make_provider(tmp_path, client)
    item = provider.search(SearchRequest("netbian")).items[0]

    detail = provider.detail(item)

    assert client.detail_calls == ["44070"]
    assert detail.images == (
        "https://pic.netbian.com/uploads/allimg/260921/151348-1789974828a29a.jpg",
    )
    assert detail.item.width == 3840
    assert detail.item.height == 2160
    assert detail.item.metadata["category"] == "4K风景"


def test_netbian_download_uses_verified_detail_url(tmp_path):
    client = FakeClient()
    downloader = FakeDownloader()
    provider = make_provider(tmp_path, client, downloader)
    item = provider.search(SearchRequest("netbian")).items[0]

    result = provider.download(item, tmp_path)

    assert result.files == ("ty-image-spider/netbian/44070.jpg",)
    assert downloader.calls == [
        (
            "https://pic.netbian.com/uploads/allimg/260921/151348-1789974828a29a.jpg",
            "44070",
            tmp_path,
        )
    ]


def test_netbian_failure_returns_cached_page(tmp_path):
    request = SearchRequest("netbian", "秋日")
    first = make_provider(tmp_path).search(request)
    failed = make_provider(
        tmp_path, FakeClient(SpiderError("timeout", "超时", status=504))
    ).search(request)

    assert first.items and failed.stale is True
    assert failed.items[0].id == "44070"
