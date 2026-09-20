"""保守匹配电影标题、上映年份与导演，不把全文相似当成同一电影。"""

from __future__ import annotations

import re
import unicodedata
from typing import Any


def normalize_title(value: str) -> str:
    value = re.sub(r"\s*\((?:19|20)\d{2}\)\s*$", "", value)
    return re.sub(
        r"[\W_]", "", unicodedata.normalize("NFKD", value).casefold(), flags=re.UNICODE
    )


def match_movies(
    movie: dict[str, Any], posts: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    names = {
        normalize_title(name)
        for name in [
            movie.get("english_title"),
            movie.get("original_title"),
            *movie.get("aliases", []),
        ]
        if name
    }
    directors = {normalize_title(name) for name in movie.get("directors", [])}
    matches = []
    for post in posts:
        if normalize_title(post["title"]) not in names:
            continue
        other_directors = {normalize_title(name) for name in post.get("directors", [])}
        same_year = bool(movie.get("year")) and movie["year"] == post.get("year")
        conflict = bool(
            directors
            and other_directors
            and not directors.intersection(other_directors)
        )
        verified = same_year and not conflict
        reason = (
            "片名与上映年份一致"
            if verified
            else "导演不同，请核对版本"
            if conflict
            else "上映年份缺失或不同，请核对版本"
        )
        matches.append({**post, "verified": verified, "reason": reason})
    return sorted(matches, key=lambda item: not item["verified"])
