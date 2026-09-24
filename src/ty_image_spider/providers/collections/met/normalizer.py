"""The Met 作品响应标准化。"""

from __future__ import annotations

from typing import Any, Mapping

from ....domain import AssetItem, SpiderError
from ...shared import HostDownloadPolicy
from ..assets import plain_text


IMAGE_POLICY = HostDownloadPolicy(
    "met", lambda host: host == "images.metmuseum.org", id_pattern=r"[1-9][0-9]*"
)


def normalize_artwork(raw: Mapping[str, Any]) -> AssetItem | None:
    object_id = raw.get("objectID")
    original = raw.get("primaryImage")
    preview = raw.get("primaryImageSmall") or original
    if (
        not isinstance(object_id, int)
        or object_id < 1
        or raw.get("isPublicDomain") is not True
        or not isinstance(original, str)
        or not isinstance(preview, str)
    ):
        return None
    try:
        IMAGE_POLICY.validate_url(original)
        IMAGE_POLICY.validate_url(preview)
    except SpiderError:
        return None
    tags_value = raw.get("tags")
    tags = (
        tuple(
            text
            for entry in tags_value
            if isinstance(entry, Mapping) and (text := plain_text(entry.get("term")))
        )
        if isinstance(tags_value, list)
        else ()
    )
    object_url = plain_text(raw.get("objectURL"))
    if not object_url.startswith("https://www.metmuseum.org/art/collection/search/"):
        object_url = f"https://www.metmuseum.org/art/collection/search/{object_id}"
    return AssetItem(
        provider="met",
        id=str(object_id),
        kind="collection",
        preview_url=preview,
        source_url=object_url,
        title=plain_text(raw.get("title")) or f"馆藏 {object_id}",
        author=plain_text(raw.get("artistDisplayName")),
        created_at=plain_text(raw.get("objectDate")),
        tags=tags[:12],
        metadata={
            "original_url": original,
            "collection": "The Metropolitan Museum of Art",
            "category": plain_text(raw.get("department")),
            "medium": plain_text(raw.get("medium")),
            "description": plain_text(raw.get("creditLine")),
            "rights": "Public Domain",
        },
    )
