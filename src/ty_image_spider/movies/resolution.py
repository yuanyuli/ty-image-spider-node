"""电影选择用例：资料库身份、来源匹配、确认与本地映射复用。"""

from __future__ import annotations

from typing import Any, Mapping

from ..models import SearchPage, SpiderError
from .filmgrab_directory import FilmGrabDirectory
from .mapping_store import MovieMappingStore
from .matching import match_movies
from .tmdb import TmdbClient


class MovieResolution:
    def __init__(
        self,
        tmdb: TmdbClient,
        directory: FilmGrabDirectory,
        mappings: MovieMappingStore,
    ) -> None:
        self._tmdb = tmdb
        self._directory = directory
        self._mappings = mappings

    def cached(self, query: str) -> dict[str, Any] | None:
        return self._mappings.find(query)

    def resolve(
        self, query: str, filters: Mapping[str, Any]
    ) -> dict[str, Any] | SearchPage:
        movie_id = _selection(filters.get("tmdb_id"))
        post_id = _selection(filters.get("filmgrab_id"))
        force = filters.get("movie_lookup") is True
        saved = self._mappings.get(movie_id) if movie_id else self._mappings.find(query)
        if saved and not force and not post_id:
            return saved
        if movie_id is None:
            movies = self._tmdb.search(query)
            if not movies:
                raise SpiderError(
                    "movie_not_found",
                    "TMDB 未找到这部电影，请尝试其他译名或补充上映年份",
                )
            return SearchPage(
                message="请选择电影及上映年份",
                choices=tuple(
                    {
                        "title": movie["title"],
                        "subtitle": f"{movie.get('year') or '年份未知'} · {movie['original_title']}",
                        "poster_url": movie["poster_url"],
                        "description": movie["overview"],
                        "source_url": f"https://www.themoviedb.org/movie/{movie['id']}",
                        "selection": {"tmdb_id": movie["id"], "movie_lookup": True},
                    }
                    for movie in movies
                ),
            )
        movie = self._tmdb.movie(movie_id)
        candidates = match_movies(movie, self._directory.find(movie))
        if not candidates:
            raise SpiderError(
                "filmgrab_movie_missing",
                f"已找到《{movie['title']}》（{movie.get('year') or '年份未知'}），但 FilmGrab 暂未找到可靠匹配的静帧条目",
            )
        if post_id:
            chosen = next((post for post in candidates if post["id"] == post_id), None)
            if chosen is None:
                raise SpiderError(
                    "invalid_movie_selection",
                    "该 FilmGrab 条目不在这部电影的候选结果中，请重新选择",
                )
            return self._mappings.save(query, movie, chosen)
        verified = [post for post in candidates if post["verified"]]
        if len(verified) == 1:
            return self._mappings.save(query, movie, verified[0])
        return SearchPage(
            message=f"请核对《{movie['title']}》（{movie.get('year') or '年份未知'}）对应的 FilmGrab 条目",
            choices=tuple(
                {
                    "title": post["title"],
                    "subtitle": f"{post.get('year') or '年份未知'} · {' / '.join(post.get('directors', []))}",
                    "poster_url": movie["poster_url"],
                    "description": post["reason"],
                    "source_url": post["source_url"],
                    "selection": {
                        "tmdb_id": movie_id,
                        "filmgrab_id": post["id"],
                        "movie_lookup": True,
                    },
                }
                for post in candidates[:20]
            ),
        )


def _selection(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise SpiderError("invalid_movie_selection", "电影选择参数无效")
    return value
