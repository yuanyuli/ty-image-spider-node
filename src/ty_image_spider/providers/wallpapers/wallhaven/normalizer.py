"""Wallhaven JSON 到领域素材的纯转换。"""

import re
from typing import Any, Mapping

from ....domain import AssetItem, JsonValue, SpiderError


_SAFE_ID = re.compile(r"^[a-z0-9]{6}$")


def normalize(raw: Mapping[str, Any]) -> AssetItem:
    item_id = str(raw.get("id") or "")
    if not _SAFE_ID.fullmatch(item_id) or str(raw.get("purity") or "") != "sfw":
        raise SpiderError(
            "wallhaven_invalid_response", "Wallhaven 返回了无效素材", status=502
        )
    thumbs = raw.get("thumbs") if isinstance(raw.get("thumbs"), Mapping) else {}
    uploader = raw.get("uploader") if isinstance(raw.get("uploader"), Mapping) else {}
    raw_tags = raw.get("tags") if isinstance(raw.get("tags"), list) else []
    tags = tuple(
        str(tag["name"])
        for tag in raw_tags
        if isinstance(tag, Mapping) and isinstance(tag.get("name"), str)
    )
    colors_value = raw.get("colors")
    colors: list[JsonValue] = (
        [str(value) for value in colors_value if isinstance(value, str)]
        if isinstance(colors_value, list)
        else []
    )
    metadata: dict[str, JsonValue] = {
        "download_url": str(raw.get("path") or ""),
        "category": str(raw.get("category") or ""),
        "purity": "sfw",
        "resolution": str(raw.get("resolution") or ""),
        "ratio": str(raw.get("ratio") or ""),
        "file_size": integer_or_none(raw.get("file_size")),
        "file_type": str(raw.get("file_type") or ""),
        "colors": colors,
        "original_source": str(raw.get("source") or ""),
    }
    return AssetItem(
        provider="wallhaven",
        id=item_id,
        preview_url=str(thumbs.get("large") or raw.get("path") or "") or None,
        source_url=str(raw.get("url") or f"https://wallhaven.cc/w/{item_id}"),
        author=str(uploader.get("username") or "") or None,
        created_at=str(raw.get("created_at") or "") or None,
        width=integer_or_none(raw.get("dimension_x")),
        height=integer_or_none(raw.get("dimension_y")),
        stats={
            "views": integer_or_zero(raw.get("views")),
            "favorites": integer_or_zero(raw.get("favorites")),
        },
        tags=tags,
        metadata=metadata,
    )


def integer_or_none(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def integer_or_zero(value: object) -> int:
    normalized = integer_or_none(value)
    return normalized if normalized is not None else 0
