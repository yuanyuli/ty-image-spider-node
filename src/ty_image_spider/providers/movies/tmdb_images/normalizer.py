"""TMDB 图片响应标准化。"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from ....domain import AssetItem


IMAGE_ROOT = "https://image.tmdb.org"
SAFE_FILE_PATH = re.compile(r"^/[A-Za-z0-9._-]+$")


def normalize_gallery(
    movie_id: int,
    movie: Mapping[str, Any],
    kind: str,
    rows: Sequence[object],
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for index, raw in enumerate(rows):
        if not isinstance(raw, Mapping):
            continue
        media_type = str(raw.get("type") or "")
        if kind != "all" and media_type != kind:
            continue
        file_path = raw.get("file_path")
        width = raw.get("width")
        height = raw.get("height")
        if (
            not isinstance(file_path, str)
            or not SAFE_FILE_PATH.fullmatch(file_path)
            or not isinstance(width, int)
            or isinstance(width, bool)
            or not isinstance(height, int)
            or isinstance(height, bool)
            or width < 1
            or height < 1
        ):
            continue
        title = str(movie.get("title") or movie.get("original_title") or "未命名电影")
        items.append(
            AssetItem(
                provider="tmdb-images",
                id=f"{movie_id}-{index}",
                preview_url=f"{IMAGE_ROOT}/t/p/w780{file_path}",
                source_url=f"https://www.themoviedb.org/movie/{movie_id}",
                title=title,
                created_at=str(movie.get("year") or "") or None,
                width=width,
                height=height,
                tags=(media_type,),
                metadata={
                    "movie_id": movie_id,
                    "file_path": file_path,
                    "media_type": media_type,
                    "original_url": f"{IMAGE_ROOT}/t/p/original{file_path}",
                    "original_title": str(movie.get("original_title") or ""),
                },
            ).to_dict()
        )
    return {"movie": dict(movie), "items": items}
