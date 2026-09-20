"""TMDB 只读电影查询，中文搜索与原名、年份、导演资料获取。"""

from __future__ import annotations

from ..version import USER_AGENT

import json
import re
from http.client import HTTPException
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from ..cache import JsonCache
from ..models import SpiderError
from ..network_retry import retry_call
from ..security import read_limited
from .credentials import TmdbCredentials


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


class TmdbClient:
    def __init__(
        self,
        credentials: TmdbCredentials,
        cache: JsonCache | None = None,
        open_url: Callable[..., Any] | None = None,
    ) -> None:
        self.credentials = credentials
        self._cache = cache
        self._open_url = open_url or build_opener(_NoRedirect()).open

    def search(self, query: str) -> list[dict[str, Any]]:
        params: dict[str, object] = {
            "query": query,
            "language": "zh-CN",
            "include_adult": "false",
            "page": 1,
        }
        year = re.search(r"[\s（(]+((?:19|20)\d{2})[）)]?$", query)
        if year:
            params.update(query=query[: year.start()].strip(), year=year[1])
        data = self._get("search/movie", params)
        if not isinstance(data.get("results"), list):
            raise SpiderError(
                "tmdb_invalid_response", "TMDB 返回的电影列表无效", status=502
            )
        return [
            _summary(raw)
            for raw in data["results"]
            if isinstance(raw, dict)
            and isinstance(raw.get("id"), int)
            and raw["id"] > 0
        ][:20]

    def movie(self, movie_id: int) -> dict[str, Any]:
        if isinstance(movie_id, bool) or not isinstance(movie_id, int) or movie_id < 1:
            raise SpiderError("invalid_movie", "电影 ID 无效")
        data = self._get(
            f"movie/{movie_id}",
            {
                "language": "en-US",
                "append_to_response": "credits,alternative_titles,translations,external_ids",
            },
        )
        if data.get("id") != movie_id:
            raise SpiderError(
                "tmdb_invalid_response", "TMDB 返回的电影身份不一致", status=502
            )
        movie = _summary(data)
        movie["english_title"] = movie["title"]
        translations = data.get("translations", {}).get("translations", [])
        for region in ("CN", "TW", "HK"):
            translated = next(
                (
                    entry.get("data", {}).get("title")
                    for entry in translations
                    if entry.get("iso_639_1") == "zh"
                    and entry.get("iso_3166_1") == region
                ),
                None,
            )
            if translated:
                movie["title"] = translated
                break
        movie["directors"] = [
            entry["name"]
            for entry in data.get("credits", {}).get("crew", [])
            if entry.get("job") == "Director" and isinstance(entry.get("name"), str)
        ]
        movie["aliases"] = list(
            dict.fromkeys(
                entry["title"]
                for entry in data.get("alternative_titles", {}).get("titles", [])
                if entry.get("iso_3166_1") in {"US", "GB"}
                and isinstance(entry.get("title"), str)
            )
        )[:8]
        movie["imdb_id"] = data.get("external_ids", {}).get("imdb_id")
        return movie

    def _get(self, path: str, params: dict[str, object]) -> dict[str, Any]:
        key = path + "?" + urlencode(params)
        cached = self._cache.get(key, 86400) if self._cache else None
        if isinstance(cached, dict):
            return cached
        token = self.credentials.read()
        if not token:
            raise SpiderError(
                "tmdb_not_configured",
                "扩展中文片名查询需要配置 TMDB API 读取令牌；已有中文片单仍可使用",
                action="注册 TMDB 后，将读取令牌填入节点目录 .local/tmdb.json 的 read_access_token",
            )
        request = Request(
            "https://api.themoviedb.org/3/" + key,
            headers={
                "Authorization": "Bearer " + token,
                "Accept": "application/json",
                "User-Agent": USER_AGENT,
            },
        )

        def fetch() -> Any:
            with self._open_url(request, timeout=20) as response:
                data = json.loads(read_limited(response, 4 * 1024 * 1024))
            return data

        try:
            data = retry_call(fetch)
            if not isinstance(data, dict):
                raise ValueError("invalid object")
        except HTTPError as exc:
            message = (
                "TMDB 读取令牌无效或未获授权，请检查本地配置"
                if exc.code in {401, 403}
                else "TMDB 请求频率过高，请稍后重试"
                if exc.code == 429
                else "TMDB 暂时无法访问，请稍后重试"
            )
            raise SpiderError("tmdb_unavailable", message, status=502) from None
        except (OSError, URLError, HTTPException, ValueError) as exc:
            raise SpiderError(
                "tmdb_unavailable", "TMDB 暂时无法访问或返回了无效数据", status=502
            ) from exc
        if self._cache:
            self._cache.put(key, data)
        return data


def _summary(raw: dict[str, Any]) -> dict[str, Any]:
    date = str(raw.get("release_date") or "")
    poster = raw.get("poster_path")
    return {
        "id": raw["id"],
        "title": str(raw.get("title") or raw.get("original_title") or "未命名电影"),
        "original_title": str(raw.get("original_title") or ""),
        "year": int(date[:4]) if len(date) >= 4 and date[:4].isdigit() else None,
        "poster_url": "https://image.tmdb.org/t/p/w185" + poster
        if isinstance(poster, str) and re.fullmatch(r"/[A-Za-z0-9._-]+", poster)
        else "",
        "overview": str(raw.get("overview") or "")[:500],
    }
