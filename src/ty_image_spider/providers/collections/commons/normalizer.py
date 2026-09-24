"""Wikimedia Commons 响应标准化。"""

from __future__ import annotations

from typing import Any, Mapping
from urllib.parse import urlsplit

from ....domain import AssetItem, SpiderError
from ...shared import HostDownloadPolicy
from ..assets import plain_text


IMAGE_POLICY = HostDownloadPolicy(
    "commons", lambda host: host == "upload.wikimedia.org", id_pattern=r"[1-9][0-9]*"
)
_PREVIEW_POLICY = HostDownloadPolicy(
    "commons-preview",
    lambda host: host in {"upload.wikimedia.org", "thumb.wikimedia.org"},
)
_SUPPORTED_IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp")


def normalize_file(raw: Mapping[str, Any]) -> AssetItem | None:
    page_id = raw.get("pageid")
    infos = raw.get("imageinfo")
    if (
        not isinstance(page_id, int)
        or page_id < 1
        or not isinstance(infos, list)
        or not infos
    ):
        return None
    info = infos[0]
    if not isinstance(info, Mapping):
        return None
    original = info.get("url")
    preview = info.get("thumburl") or original
    try:
        if not isinstance(original, str) or not isinstance(preview, str):
            return None
        if not urlsplit(original).path.casefold().endswith(_SUPPORTED_IMAGE_SUFFIXES):
            return None
        IMAGE_POLICY.validate_url(original)
        _PREVIEW_POLICY.validate_url(preview)
    except SpiderError:
        return None
    metadata = info.get("extmetadata")
    values = metadata if isinstance(metadata, Mapping) else {}
    title = _meta(values, "ObjectName") or plain_text(raw.get("title")).removeprefix(
        "File:"
    )
    rights = _meta(values, "LicenseShortName") or _meta(values, "UsageTerms")
    return AssetItem(
        provider="commons",
        id=str(page_id),
        kind="collection",
        preview_url=preview,
        source_url=str(info.get("descriptionurl") or ""),
        title=title,
        author=_meta(values, "Artist"),
        created_at=_meta(values, "DateTimeOriginal"),
        width=_positive_int(info.get("width")),
        height=_positive_int(info.get("height")),
        metadata={
            "original_url": original,
            "collection": "Wikimedia Commons",
            "rights": rights or "使用条件见来源页面",
            "usage_terms": _meta(values, "UsageTerms"),
            "license_url": _meta(values, "LicenseUrl"),
            "attribution_required": _meta(values, "AttributionRequired").casefold()
            == "true",
            "description": _meta(values, "ImageDescription"),
        },
    )


def _meta(values: Mapping[str, Any], name: str) -> str:
    entry = values.get(name)
    return plain_text(entry.get("value")) if isinstance(entry, Mapping) else ""


def _positive_int(value: object) -> int | None:
    return (
        value
        if isinstance(value, int) and not isinstance(value, bool) and value > 0
        else None
    )
