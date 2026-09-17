import json
from pathlib import Path

from ty_image_spider.cache import JsonCache
from ty_image_spider.models import DownloadResult, SearchRequest, SpiderError
from ty_image_spider.providers.wallhaven import WallhavenProvider
from ty_image_spider.providers.wallhaven_client import WallhavenPage


FIXTURES = Path(__file__).parent / "fixtures"
SEARCH = json.loads((FIXTURES / "wallhaven_search.json").read_text())
DETAIL = json.loads((FIXTURES / "wallhaven_detail.json").read_text())["data"]


class FakeClient:
    def __init__(self, error=None):
        self.error = error
        self.search_calls = []
        self.detail_calls = []

    def search(self, params):
        self.search_calls.append(params)
        if self.error:
            raise self.error
        return WallhavenPage(tuple(SEARCH["data"]), 1, 3)

    def detail(self, item_id):
        self.detail_calls.append(item_id)
        return DETAIL


class FakeDownloader:
    def __init__(self):
        self.calls = []

    def download(self, url, item_id, output_root):
        self.calls.append((url, item_id, output_root))
        return DownloadResult((f"ty-image-spider/wallhaven/{item_id}.jpg",), "已下载")


def make_provider(tmp_path, client=None, downloader=None):
    return WallhavenProvider(
        client or FakeClient(), JsonCache(tmp_path), downloader or FakeDownloader()
    )


def test_wallhaven_descriptor_exposes_source_specific_filters(tmp_path):
    descriptor = make_provider(tmp_path).descriptor()

    assert descriptor.id == "wallhaven"
    assert descriptor.capabilities.bulk_download is True
    assert descriptor.capabilities.pagination == "page"
    assert {field.name for field in descriptor.filters} == {
        "category",
        "sorting",
        "top_range",
        "orientation",
        "atleast",
    }


def test_wallhaven_provider_maps_filters_and_normalizes_items(tmp_path):
    client = FakeClient()
    page = make_provider(tmp_path, client).search(
        SearchRequest(
            "wallhaven",
            "night city",
            {
                "category": "people",
                "sorting": "toplist",
                "top_range": "1M",
                "orientation": "portrait",
                "atleast": "1920x1080",
            },
            cursor="2",
        )
    )

    assert client.search_calls == [
        {
            "q": "night city",
            "categories": "001",
            "purity": "100",
            "sorting": "toplist",
            "order": "desc",
            "topRange": "1M",
            "ratios": "portrait",
            "atleast": "1920x1080",
            "page": 2,
        }
    ]
    assert page.next_cursor == "2"
    assert page.items[0].id == "zp9vkg"
    assert page.items[0].preview_url.endswith("zp9vkg.jpg")
    assert page.items[0].source_url == "https://wallhaven.cc/w/zp9vkg"
    assert page.items[0].stats == {"views": 2381, "favorites": 42}
    assert page.items[0].metadata["download_url"].startswith("https://w.wallhaven.cc/")


def test_wallhaven_detail_adds_author_tags_and_full_image(tmp_path):
    client = FakeClient()
    provider = make_provider(tmp_path, client)
    item = provider.search(SearchRequest("wallhaven")).items[0]

    detail = provider.detail(item)

    assert client.detail_calls == ["zp9vkg"]
    assert detail.item.author == "wall-user"
    assert detail.item.tags == ("mountains", "night")
    assert detail.images == ("https://w.wallhaven.cc/full/zp/wallhaven-zp9vkg.jpg",)


def test_wallhaven_failure_returns_stale_cached_page(tmp_path):
    request = SearchRequest("wallhaven", "forest")
    first = make_provider(tmp_path).search(request)
    failed = make_provider(
        tmp_path, FakeClient(SpiderError("wallhaven_timeout", "超时", status=504))
    ).search(request)

    assert first.items
    assert failed.stale is True
    assert failed.items[0].id == first.items[0].id


def test_wallhaven_rejects_foreign_item_and_uses_download_url(tmp_path):
    provider = make_provider(tmp_path)
    item = provider.search(SearchRequest("wallhaven")).items[0]

    assert provider.download(item, tmp_path).files == (
        "ty-image-spider/wallhaven/zp9vkg.jpg",
    )

    foreign = item.__class__(provider="civitai", id=item.id)
    try:
        provider.download(foreign, tmp_path)
    except SpiderError as exc:
        assert exc.code == "invalid_asset"
    else:
        raise AssertionError("应拒绝其他来源的素材")


def test_wallhaven_download_uses_server_verified_sfw_url(tmp_path):
    client = FakeClient()
    downloader = FakeDownloader()
    provider = make_provider(tmp_path, client, downloader)
    forged = (
        provider.search(SearchRequest("wallhaven"))
        .items[0]
        .__class__(
            provider="wallhaven",
            id="zp9vkg",
            metadata={
                "purity": "nsfw",
                "download_url": "https://w.wallhaven.cc/full/xx/wallhaven-xxxxxx.jpg",
            },
        )
    )

    provider.download(forged, tmp_path)

    assert client.detail_calls == ["zp9vkg"]
    assert downloader.calls == [
        (
            "https://w.wallhaven.cc/full/zp/wallhaven-zp9vkg.jpg",
            "zp9vkg",
            tmp_path,
        )
    ]


def test_wallhaven_download_rejects_non_sfw_server_detail(tmp_path):
    client = FakeClient()
    client_detail = dict(DETAIL)
    client_detail["purity"] = "nsfw"
    client.detail = lambda item_id: client_detail
    downloader = FakeDownloader()
    provider = make_provider(tmp_path, client, downloader)
    item = provider.search(SearchRequest("wallhaven")).items[0]

    try:
        provider.download(item, tmp_path)
    except SpiderError as exc:
        assert exc.code == "wallhaven_invalid_response"
    else:
        raise AssertionError("应拒绝非 SFW 的服务端详情")

    assert downloader.calls == []


def test_wallhaven_provider_does_not_truncate_valid_large_page_number(tmp_path):
    client = FakeClient()

    make_provider(tmp_path, client).search(
        SearchRequest("wallhaven", "nature", cursor="10001")
    )

    assert client.search_calls[0]["page"] == 10001
