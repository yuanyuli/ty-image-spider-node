from dataclasses import replace
from io import BytesIO
import json
from urllib.parse import parse_qs, urlsplit

import pytest

from ty_image_spider.models import DownloadResult, SearchRequest, SpiderError
from ty_image_spider.cache import JsonCache
from ty_image_spider.providers.public_json_client import PublicJsonClient
from ty_image_spider.providers.editorial import EditorialProvider
from ty_image_spider.providers.editorial_sources import COLOSSAL, DESIGN_MILK
from ty_image_spider.providers.arena import ArenaProvider


class Response(BytesIO):
    def __init__(self, data, url, pages=2):
        super().__init__(json.dumps(data).encode())
        self.url = url
        self.headers = {"X-WP-TotalPages": str(pages)}

    def geturl(self):
        return self.url


def client(root, rows, calls):
    def read(request, timeout):
        calls.append(request.full_url)
        return Response(rows.pop(0), request.full_url)

    return PublicJsonClient(root, "测试来源", open_url=read)


def post():
    root = "https://www.thisiscolossal.com/wp-content/uploads/2026/09/"
    return {
        "id": 42,
        "title": {"rendered": "Photo &amp; Design"},
        "link": "https://www.thisiscolossal.com/2026/09/example/",
        "date": "2026-09-20",
        "excerpt": {"rendered": "<p>作品说明</p>"},
        "content": {
            "rendered": f'<img src="{root}a.jpg"><img src="{root}b-small.jpg" srcset="{root}b-small.jpg 300w, {root}b.jpg 1600w"><img src="{root}a.jpg"><img src="https://evil.test/tracker.jpg"><script><img src="{root}fake.jpg"></script>'
        },
        "_embedded": {
            "wp:featuredmedia": [
                {
                    "source_url": root + "a.jpg",
                    "media_details": {
                        "sizes": {
                            "medium_large": {"source_url": root + "a-preview.jpg"}
                        }
                    },
                }
            ]
        },
    }


def test_editorial_real_category_pagination_and_deduplicated_gallery():
    calls = []
    provider = EditorialProvider(
        COLOSSAL, client(COLOSSAL.api_root, [[post()], [post()]], calls)
    )
    page = provider.search(
        SearchRequest("colossal", "portrait", {"category": "photography"})
    )
    query = parse_qs(urlsplit(calls[0]).query)
    assert query["categories"] == ["496"] and query["search"] == ["portrait"]
    assert page.next_cursor == "2" and page.items[0].title == "Photo & Design"
    item = page.items[0]
    assert item.image_count == 2 and item.download_mode == "gallery"
    detail = provider.detail(item)
    assert detail.content == "作品说明"
    assert [url.rsplit("/", 1)[1] for url in detail.images] == ["a.jpg", "b.jpg"]
    assert provider.search(SearchRequest("colossal", cursor="2")).next_cursor is None


def test_designmilk_graphic_filter_uses_tag_not_category():
    calls = []
    provider = EditorialProvider(DESIGN_MILK, client(DESIGN_MILK.api_root, [[]], calls))
    page = provider.search(SearchRequest("designmilk", filters={"category": "graphic"}))
    query = parse_qs(urlsplit(calls[0]).query)
    assert query["tags"] == ["206"] and "categories" not in query
    assert not page.items and page.next_cursor == "2"


def test_editorial_partial_download_reports_saved_files(tmp_path):
    class Downloader:
        def download(self, url, provider, item_id, output):
            if url.endswith("b.jpg"):
                raise SpiderError("download_failed", "失败")
            return DownloadResult((f"ty-image-spider/{provider}/{item_id}.jpg",))

    provider = EditorialProvider(
        COLOSSAL, client(COLOSSAL.api_root, [[post()]], []), Downloader()
    )
    item = provider.search(SearchRequest("colossal")).items[0]
    result = provider.download(item, tmp_path)
    assert result.files == ("ty-image-spider/colossal/42-1.jpg",)
    assert "失败 1" in result.message
    with pytest.raises(SpiderError):
        provider.detail(replace(item, metadata={"images": ["https://evil.test/a.jpg"]}))


def block(item_id=10):
    return {
        "id": item_id,
        "class": "Image",
        "title": "Poster",
        "visibility": "public",
        "image": {
            "thumb": {"url": "https://images.are.na/thumb"},
            "original": {
                "url": f"https://d2w9rnfcy7mm78.cloudfront.net/{item_id}/poster.jpg"
            },
        },
        "user": {"full_name": "收藏者"},
    }


def test_arena_channel_url_real_pagination_skips_nonimage_blocks():
    calls = []
    data = {
        "length": 30,
        "contents": [
            block(),
            {"id": 2, "class": "Text"},
            {**block(3), "visibility": "private"},
        ],
    }
    provider = ArenaProvider(client("https://api.are.na/v2/", [data], calls))
    page = provider.search(
        SearchRequest("arena", "https://www.are.na/designer/my-board", cursor="2")
    )
    assert "/channels/my-board?" in calls[0]
    assert parse_qs(urlsplit(calls[0]).query)["page"] == ["2"]
    assert len(page.items) == 1 and page.next_cursor is None
    assert page.items[0].author == "收藏：收藏者"
    detail = provider.detail(page.items[0])
    assert detail.images[0].endswith("poster.jpg")
    assert detail.item.preview_url.endswith("poster.jpg")


@pytest.mark.parametrize(
    "query",
    [
        "https://evil.test/board",
        "https://www.are.na/u/../bad",
        "https://www.are.na:bad/u/board",
        "海报",
    ],
)
def test_arena_rejects_non_channel_query_before_network(query):
    def unexpected(*args, **kwargs):
        pytest.fail("不应访问网络")

    provider = ArenaProvider(
        PublicJsonClient("https://api.are.na/v2/", "Are.na", open_url=unexpected)
    )
    with pytest.raises(SpiderError, match="频道"):
        provider.search(SearchRequest("arena", query))


def test_public_client_preserves_pagination_headers_in_cache_and_refresh(tmp_path):
    calls = []

    def read(request, timeout):
        calls.append(request.full_url)
        return Response([], request.full_url, pages=len(calls) + 2)

    api = PublicJsonClient(COLOSSAL.api_root, "Colossal", JsonCache(tmp_path), read)
    assert api.get("posts", {"page": 1}).total_pages == 3
    assert api.get("posts", {"page": 1}).total_pages == 3
    assert api.get("posts", {"page": 2}).total_pages == 4
    assert api.get("posts", {"page": 1}, refresh=True).total_pages == 5


def test_public_client_rejects_cross_host_response():
    api = PublicJsonClient(
        COLOSSAL.api_root,
        "Colossal",
        open_url=lambda *a, **k: Response([], "https://evil.test/posts"),
    )
    with pytest.raises(SpiderError):
        api.get("posts", {})
