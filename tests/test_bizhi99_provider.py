from pathlib import Path

from ty_image_spider.infrastructure.cache import JsonCache
from ty_image_spider.domain import DownloadResult, SearchRequest, SpiderError
from ty_image_spider.providers.bizhi99 import Bizhi99ListPage, Bizhi99Provider


FIXTURES = Path(__file__).parent / "fixtures"


class FakeClient:
    def __init__(self, error=None):
        self.error = error
        self.list_calls = []
        self.detail_calls = []

    def list(self, path, page):
        self.list_calls.append((path, page))
        if self.error:
            raise self.error
        return Bizhi99ListPage(
            FIXTURES.joinpath("bizhi99_list.html").read_text(encoding="utf-8"), page, 2
        )

    def detail(self, item_id):
        self.detail_calls.append(item_id)
        return FIXTURES.joinpath("bizhi99_detail.html").read_text(encoding="utf-8")


class FakeDownloader:
    def __init__(self):
        self.calls = []

    def download(self, url, item_id, output_root):
        self.calls.append((url, item_id, output_root))
        return DownloadResult((f"ty-image-spider/bizhi99/{item_id}.jpg",), "已下载")


def make_provider(tmp_path, client=None, downloader=None):
    return Bizhi99Provider(
        client or FakeClient(), JsonCache(tmp_path), downloader or FakeDownloader()
    )


def test_bizhi99_descriptor_is_wallpaper_source(tmp_path):
    descriptor = make_provider(tmp_path).descriptor()

    assert descriptor.id == "bizhi99"
    assert descriptor.presentation.group_id == "wallpaper"
    assert descriptor.capabilities.bulk_download is True
    assert {field.name for field in descriptor.filters} == {"category"}


def test_bizhi99_search_maps_category_and_parses_lazy_image(tmp_path):
    client = FakeClient()
    page = make_provider(tmp_path, client).search(
        SearchRequest("bizhi99", filters={"category": "landscape"})
    )

    assert client.list_calls == [("/c2/", 1)]
    assert page.next_cursor == "2"
    assert page.items[0].id == "12495"
    assert page.items[0].title == "风景自然风光山川森林高清壁纸"
    assert page.items[0].preview_url.startswith("https://pic.bizhi66.com/pic/")


def test_bizhi99_detail_and_download_use_original_url(tmp_path):
    client = FakeClient()
    downloader = FakeDownloader()
    provider = make_provider(tmp_path, client, downloader)
    item = provider.search(SearchRequest("bizhi99")).items[0]

    detail = provider.detail(item)
    assert detail.images == (
        "https://pic.bizhi66.com/pic/7a79a461cad6bb14f0685771a59ae6a4",
    )
    assert (detail.item.width, detail.item.height) == (3840, 2400)

    provider.download(item, tmp_path)
    assert downloader.calls == [
        (
            "https://pic.bizhi66.com/pic/7a79a461cad6bb14f0685771a59ae6a4",
            "12495",
            tmp_path,
        )
    ]


def test_bizhi99_failure_returns_cached_page(tmp_path):
    request = SearchRequest("bizhi99")
    first = make_provider(tmp_path).search(request)
    failed = make_provider(
        tmp_path, FakeClient(SpiderError("timeout", "超时", status=504))
    ).search(request)

    assert first.items and failed.stale is True
