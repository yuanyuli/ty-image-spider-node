from gzip import compress
from io import BytesIO

from ty_image_spider.infrastructure.cache import JsonCache
from ty_image_spider.domain import DownloadResult, SearchRequest
from ty_image_spider.providers.wallpaperscraft import (
    WallpapersCraftClient,
    WallpapersCraftPage,
    WallpapersCraftProvider,
)


LIST_HTML = """
<ul class="wallpapers__list">
<li class="wallpapers__item"><a class="wallpapers__link" href="/download/boat_mountains_lake_135258/1920x1080"><img class="wallpapers__image" src="https://images.wallpaperscraft.com/image/single/boat_mountains_lake_135258_300x168.jpg" alt="Preview wallpaper boat, mountains, lake"></a></li>
</ul><a href="/catalog/nature/1920x1080/page2">2</a>
"""
DETAIL_HTML = """
<h1>Boat, mountains and lake wallpaper</h1>
<img src="https://images.wallpaperscraft.com/image/single/boat_mountains_lake_135258_1920x1080.jpg">
"""


class FakeClient:
    def __init__(self):
        self.list_calls = []
        self.detail_calls = []

    def list(self, category, resolution, query, page):
        self.list_calls.append((category, resolution, query, page))
        return WallpapersCraftPage(LIST_HTML, page, 2)

    def detail(self, path):
        self.detail_calls.append(path)
        return DETAIL_HTML


class FakeDownloader:
    def __init__(self):
        self.calls = []

    def download(self, url, item_id, output_root):
        self.calls.append((url, item_id, output_root))
        return DownloadResult((f"ty-image-spider/wallpaperscraft/{item_id}.jpg",))


def make_provider(tmp_path, client=None, downloader=None):
    return WallpapersCraftProvider(
        client or FakeClient(), JsonCache(tmp_path), downloader or FakeDownloader()
    )


def test_wallpaperscraft_maps_filters_and_parses_list(tmp_path):
    client = FakeClient()
    page = make_provider(tmp_path, client).search(
        SearchRequest(
            "wallpaperscraft",
            "mountain",
            {"category": "nature", "resolution": "1920x1080"},
        )
    )

    assert client.list_calls == [("nature", "1920x1080", "mountain", 1)]
    assert page.next_cursor == "2"
    assert page.items[0].id == "135258-1920x1080"
    assert page.items[0].title == "boat, mountains, lake"
    assert page.items[0].width == 1920 and page.items[0].height == 1080


def test_wallpaperscraft_detail_and_download_verify_original(tmp_path):
    client = FakeClient()
    downloader = FakeDownloader()
    provider = make_provider(tmp_path, client, downloader)
    item = provider.search(SearchRequest("wallpaperscraft")).items[0]

    detail = provider.detail(item)
    assert detail.images == (
        "https://images.wallpaperscraft.com/image/single/boat_mountains_lake_135258_1920x1080.jpg",
    )
    provider.download(item, tmp_path)
    assert downloader.calls[0][0] == detail.images[0]


def test_wallpaperscraft_descriptor_uses_wallpaper_group(tmp_path):
    descriptor = make_provider(tmp_path).descriptor()
    assert descriptor.presentation.group_id == "wallpaper"
    assert descriptor.capabilities.cache is True
    assert {field.name for field in descriptor.filters} == {"category", "resolution"}


def test_wallpaperscraft_client_decodes_gzip_html():
    class Response(BytesIO):
        headers = {"Content-Encoding": "gzip"}

        def geturl(self):
            return "https://wallpaperscraft.com/catalog/nature/1920x1080"

    client = WallpapersCraftClient(
        open_url=lambda request, timeout: Response(compress(LIST_HTML.encode()))
    )

    page = client.list("nature", "1920x1080", "", 1)
    assert "wallpapers__image" in page.html
    assert page.last_page == 2
