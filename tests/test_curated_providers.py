from ty_image_spider.models import SearchRequest
from ty_image_spider.providers.behance import BehanceProvider
from ty_image_spider.providers.filmgrab import FilmGrabProvider
from ty_image_spider.providers.curated_client import parse_project_images
from ty_image_spider.cache import JsonCache
from ty_image_spider.models import SpiderError
import pytest


class BehanceClientStub:
    def images(self, item_id):
        return (
            "https://mir-s3-cdn-cf.behance.net/project_modules/1400/abcdef42.test.jpg",
        )

    def projects(self, category, query, cursor=None):
        assert category == "photography"
        assert query == ""
        return [
            {
                "id": 42,
                "name": "Quiet Light",
                "url": "https://www.behance.net/gallery/42/Quiet-Light",
                "covers": {
                    "allAvailable": [
                        {
                            "url": "https://mir-s3-cdn-cf.behance.net/projects/404/a.jpg",
                            "width": 404,
                        },
                        {
                            "url": "https://mir-s3-cdn-cf.behance.net/projects/original/a.jpg",
                            "width": None,
                        },
                    ]
                },
                "owners": [{"displayName": "Artist"}],
            }
        ], "MjQ=" if cursor is None else None


class FilmGrabClientStub:
    def posts(self, query, page):
        assert query == "Blade Runner"
        return (
            [
                {
                    "id": 12,
                    "link": "https://film-grab.com/blade-runner/",
                    "title": {"rendered": "Blade Runner"},
                    "content": {
                        "rendered": (
                            '<a class="bwg-a" data-image-id="77" '
                            'href="https://film-grab.com/wp-content/uploads/photo-gallery/one.jpg">'
                            '<img src="https://film-grab.com/wp-content/uploads/photo-gallery/thumb/one.jpg"></a>'
                        )
                    },
                }
            ],
            2,
        )


class ManyFramesClient:
    def posts(self, query, page):
        images = "".join(
            f'<a class="bwg-a" data-image-id="{index}" href="https://film-grab.com/wp-content/uploads/photo-gallery/{index}.jpg"><img src="https://film-grab.com/wp-content/uploads/photo-gallery/thumb/{index}.jpg"></a>'
            for index in range(1, 31)
        )
        return (
            [{"id": 9, "title": {"rendered": "Film"}, "content": {"rendered": images}}],
            1,
        )


def test_behance_gallery_normalizes_cover_and_author(tmp_path):
    provider = BehanceProvider(BehanceClientStub())
    page = provider.search(
        SearchRequest("behance", filters={"category": "photography"})
    )
    assert len(page.items) == 1
    assert page.next_cursor == "MjQ="
    assert page.items[0].id == "42"
    assert page.items[0].author == "Artist"
    assert "/404/" in page.items[0].preview_url
    assert "/project_modules/" in provider.detail(page.items[0]).images[0]


def test_behance_forwards_cursor_and_stops_at_last_page():
    provider = BehanceProvider(BehanceClientStub())
    page = provider.search(
        SearchRequest("behance", filters={"category": "photography"}, cursor="MjQ=")
    )
    assert len(page.items) == 1
    assert page.next_cursor is None


def test_filmgrab_accepts_chinese_title_and_exposes_chinese_presets():
    provider = FilmGrabProvider(FilmGrabClientStub())
    page = provider.search(SearchRequest("filmgrab", query="银翼杀手"))
    assert len(page.items) == 1
    assert any(
        option.value == "银翼杀手" for option in provider.descriptor().search_presets
    )


def test_filmgrab_unknown_chinese_title_has_actionable_message():
    provider = FilmGrabProvider(FilmGrabClientStub())
    with pytest.raises(SpiderError, match="中文片单"):
        provider.search(SearchRequest("filmgrab", query="尚未收录的电影名称"))


def test_filmgrab_uses_stable_frame_id_and_original_image():
    provider = FilmGrabProvider(FilmGrabClientStub())
    page = provider.search(SearchRequest("filmgrab", query="Blade Runner"))
    assert page.next_cursor == "2"
    assert len(page.items) == 1
    assert page.items[0].id == "12-77"
    assert "/thumb/" in page.items[0].preview_url
    assert "/thumb/" not in provider.detail(page.items[0]).images[0]


def test_filmgrab_limits_gallery_page_to_bulk_download_capacity():
    provider = FilmGrabProvider(ManyFramesClient())
    first = provider.search(SearchRequest("filmgrab"))
    assert len(first.items) == 24
    assert first.next_cursor == "1:24"
    second = provider.search(SearchRequest("filmgrab", cursor=first.next_cursor))
    assert len(second.items) == 6
    assert second.next_cursor is None


def test_behance_project_images_exclude_recommendations_and_duplicates():
    markup = (
        '<img src="https://mir-s3-cdn-cf.behance.net/project_modules/1400/abcdef42.test.jpg">'
        * 2
    )
    markup += '<img src="https://mir-s3-cdn-cf.behance.net/project_modules/1400/abcdef43.test.jpg">'
    assert parse_project_images(markup, "42") == (
        "https://mir-s3-cdn-cf.behance.net/project_modules/1400/abcdef42.test.jpg",
    )


def test_filmgrab_reuses_article_for_frame_pages_and_falls_back_on_network_failure(
    tmp_path,
):
    class Client(ManyFramesClient):
        calls = 0
        fail = False

        def posts(self, query, page):
            self.calls += 1
            if self.fail:
                raise SpiderError("filmgrab_unavailable", "来源暂时不可用", status=502)
            return super().posts(query, page)

    client = Client()
    provider = FilmGrabProvider(client, cache=JsonCache(tmp_path))
    first = provider.search(SearchRequest("filmgrab"))
    second = provider.search(SearchRequest("filmgrab", cursor=first.next_cursor))
    assert len(second.items) == 6
    assert client.calls == 1
    client.fail = True
    offline = provider.search(SearchRequest("filmgrab", refresh=True))
    assert offline.stale
    assert len(offline.items) == 24
