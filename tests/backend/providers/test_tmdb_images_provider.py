import pytest

from ty_image_spider.infrastructure.cache import JsonCache
from ty_image_spider.domain import DownloadResult, SearchRequest, SpiderError
from ty_image_spider.providers.movies.tmdb_images import TmdbImageProvider


class FakeClient:
    def __init__(self, configured=True):
        self.configured_value = configured
        self.search_calls = []
        self.image_calls = []
        self.movie_calls = []

    def has_credentials(self):
        return self.configured_value

    def search(self, query):
        self.search_calls.append(query)
        return [
            {
                "id": 129,
                "title": "千与千寻",
                "original_title": "Spirited Away",
                "year": 2001,
            }
        ]

    def movie(self, movie_id):
        self.movie_calls.append(movie_id)
        return {
            "id": movie_id,
            "title": "千与千寻",
            "original_title": "Spirited Away",
            "year": 2001,
        }

    def images(self, movie_id):
        self.image_calls.append(movie_id)
        return [
            {
                "file_path": "/abc123.jpg",
                "width": 1920,
                "height": 1080,
                "type": "backdrop",
            },
            {
                "file_path": "/poster.jpg",
                "width": 500,
                "height": 750,
                "type": "poster",
            },
        ]


class FakeDownloader:
    def __init__(self):
        self.calls = []

    def download(self, url, item_id, output_root):
        self.calls.append((url, item_id, output_root))
        return DownloadResult((f"ty-image-spider/tmdb-images/{item_id}.jpg",), "已下载")


def make_provider(tmp_path, client=None, downloader=None):
    return TmdbImageProvider(
        client or FakeClient(), JsonCache(tmp_path), downloader or FakeDownloader()
    )


def test_descriptor_places_tmdb_images_in_movie_group(tmp_path):
    descriptor = make_provider(tmp_path).descriptor()

    assert descriptor.id == "tmdb-images"
    assert descriptor.presentation.group_id == "cinema"
    assert descriptor.capabilities.bulk_download is True
    assert {field.name for field in descriptor.filters} == {"type"}


def test_search_resolves_chinese_movie_and_filters_static_backdrops(tmp_path):
    client = FakeClient()
    page = make_provider(tmp_path, client).search(
        SearchRequest("tmdb-images", "千与千寻", {"type": "backdrop"})
    )

    assert client.search_calls == ["千与千寻"]
    assert client.image_calls == [129]
    assert len(page.items) == 1
    assert page.items[0].id == "129-0"
    assert page.items[0].title == "千与千寻"
    assert page.items[0].width == 1920
    assert page.items[0].preview_url.endswith("/w780/abc123.jpg")
    assert page.items[0].metadata["original_url"].endswith("/original/abc123.jpg")


def test_detail_and_download_reverify_tmdb_image(tmp_path):
    client = FakeClient()
    downloader = FakeDownloader()
    provider = make_provider(tmp_path, client, downloader)
    item = provider.search(SearchRequest("tmdb-images", "千与千寻")).items[0]

    detail = provider.detail(item)
    assert detail.images == ("https://image.tmdb.org/t/p/original/abc123.jpg",)

    provider.download(item, tmp_path)
    assert downloader.calls == [
        (
            "https://image.tmdb.org/t/p/original/abc123.jpg",
            "129-0",
            tmp_path,
        )
    ]
    assert client.image_calls == [129, 129, 129]


def test_tmdb_images_rejects_forged_image_path(tmp_path):
    provider = make_provider(tmp_path)
    item = provider.search(SearchRequest("tmdb-images", "千与千寻")).items[0]
    forged = item.__class__(
        provider=item.provider,
        id=item.id,
        metadata={"movie_id": 129, "file_path": "/evil.test/x.jpg"},
    )

    with pytest.raises(SpiderError, match="图片"):
        provider.detail(forged)


def test_tmdb_images_reports_missing_token(tmp_path):
    provider = make_provider(tmp_path, FakeClient(configured=False))

    assert provider.status().available is False
    with pytest.raises(SpiderError, match="令牌"):
        provider.search(SearchRequest("tmdb-images", "千与千寻"))
