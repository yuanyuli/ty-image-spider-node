"""读取 FilmGrab 电影分类年份与导演，供身份匹配使用。"""

from __future__ import annotations

import re
from html import unescape
from typing import Any, Mapping

from ..cache import JsonCache
from ..providers.curated_client import FilmGrabClient
from .matching import normalize_title


class FilmGrabDirectory:
    def __init__(self, client: FilmGrabClient, cache: JsonCache) -> None:
        self._client = client
        self._cache = cache

    def find(self, movie: dict[str, Any]) -> list[dict[str, Any]]:
        terms = list(
            dict.fromkeys(
                name
                for name in [
                    movie.get("english_title"),
                    movie.get("original_title"),
                    *movie.get("aliases", []),
                ]
                if name
            )
        )[:3]
        results: dict[int, dict[str, Any]] = {}
        searched: set[str] = set()
        for term in terms:
            normalized = normalize_title(term)
            if normalized in searched:
                continue
            searched.add(normalized)
            posts = self._cache.get(term, 3600)
            if not isinstance(posts, list):
                posts = [
                    parse_filmgrab_movie(raw) for raw in self._client.catalogue(term)
                ]
                self._cache.put(term, posts)
            for post in posts:
                if post["id"] > 0:
                    results[post["id"]] = post
        return list(results.values())


def parse_filmgrab_movie(raw: Mapping[str, Any]) -> dict[str, Any]:
    title = unescape(str(raw.get("title", {}).get("rendered") or ""))
    terms = [
        entry
        for group in raw.get("_embedded", {}).get("wp:term", [])
        if isinstance(group, list)
        for entry in group
        if isinstance(entry, dict)
    ]
    year = next(
        (
            int(term["name"])
            for term in terms
            if re.fullmatch(r"(?:18|19|20)\d{2}", str(term.get("name", "")))
        ),
        None,
    )
    if year is None:
        match = re.search(r"\(((?:18|19|20)\d{2})\)$", title)
        year = int(match[1]) if match else None
    directors = [
        unescape(term["name"])
        for term in terms
        if "/category/directors/" in str(term.get("link", ""))
        and isinstance(term.get("name"), str)
    ]
    return {
        "id": int(raw.get("id") or 0),
        "title": title,
        "year": year,
        "directors": directors,
        "source_url": str(raw.get("link") or ""),
    }
