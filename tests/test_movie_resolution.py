import pytest

from ty_image_spider.models import SearchPage, SpiderError
from ty_image_spider.movies.mapping_store import MovieMappingStore
from ty_image_spider.movies.resolution import MovieResolution


MOVIE = {
    "id": 680,
    "title": "低俗小说",
    "english_title": "Pulp Fiction",
    "original_title": "Pulp Fiction",
    "year": 1994,
    "directors": ["Quentin Tarantino"],
    "poster_url": "",
    "overview": "",
}
POST = {
    "id": 42,
    "title": "Pulp Fiction",
    "year": 1994,
    "directors": ["Quentin Tarantino"],
    "source_url": "https://film-grab.com/pulp-fiction/",
}


class Tmdb:
    def search(self, query):
        return [MOVIE]

    def movie(self, movie_id):
        assert movie_id == 680
        return MOVIE


class Directory:
    def __init__(self, posts):
        self.posts = posts

    def find(self, movie):
        return self.posts


def test_identity_selection_exact_mapping_and_reuse_after_restart(tmp_path):
    path = tmp_path / "mapping.sqlite3"
    resolver = MovieResolution(Tmdb(), Directory([POST]), MovieMappingStore(path))
    choices = resolver.resolve("低俗小说", {})
    assert isinstance(choices, SearchPage)
    selected = resolver.resolve("低俗小说", choices.choices[0]["selection"])
    assert selected["post"]["id"] == 42
    # 确认后的映射无需再次访问资料库或来源索引。
    offline = MovieResolution(None, None, MovieMappingStore(path))
    assert offline.resolve("低俗小说", {})["movie"]["id"] == 680


def test_unverified_year_requires_explicit_valid_candidate(tmp_path):
    resolver = MovieResolution(
        Tmdb(),
        Directory([{**POST, "year": None}]),
        MovieMappingStore(tmp_path / "map.sqlite3"),
    )
    page = resolver.resolve("低俗小说", {"tmdb_id": 680})
    assert isinstance(page, SearchPage)
    assert resolver.cached("低俗小说") is None
    with pytest.raises(SpiderError, match="不在"):
        resolver.resolve("低俗小说", {"tmdb_id": 680, "filmgrab_id": 99})
    assert (
        resolver.resolve("低俗小说", page.choices[0]["selection"])["post"]["id"] == 42
    )


def test_missing_source_movie_is_distinct_from_missing_tmdb_movie(tmp_path):
    resolver = MovieResolution(
        Tmdb(), Directory([]), MovieMappingStore(tmp_path / "map.sqlite3")
    )
    with pytest.raises(SpiderError, match="已找到.*FilmGrab"):
        resolver.resolve("低俗小说", {"tmdb_id": 680})
    assert resolver.cached("低俗小说") is None


def test_force_lookup_offers_versions_even_when_query_has_saved_mapping(tmp_path):
    resolver = MovieResolution(
        Tmdb(), Directory([POST]), MovieMappingStore(tmp_path / "map.sqlite3")
    )
    resolver.resolve("低俗小说", {"tmdb_id": 680})
    assert isinstance(resolver.resolve("低俗小说", {"movie_lookup": True}), SearchPage)
