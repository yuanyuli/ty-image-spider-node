"""Prelinger 不可信响应到稳定视频领域模型的纯转换。"""

from __future__ import annotations

import re
from dataclasses import replace
from typing import Mapping
from urllib.parse import quote

from ....domain import AssetDetail, AssetItem, MediaResource
from ...collections.assets import plain_text


SAFE_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
_SAFE_FILE = re.compile(r"[^/\\]+\.mp4", re.IGNORECASE)


def normalize_search_item(raw: Mapping[str, object]) -> AssetItem | None:
    identifier = raw.get("identifier")
    if not isinstance(identifier, str) or not SAFE_IDENTIFIER.fullmatch(identifier):
        return None
    return AssetItem(
        provider="prelinger",
        id=identifier,
        kind="video",
        preview_url=f"https://archive.org/services/img/{quote(identifier, safe='')}",
        source_url=f"https://archive.org/details/{quote(identifier, safe='')}",
        title=plain_text(raw.get("title")) or identifier,
        author=plain_text(raw.get("creator")) or None,
        created_at=plain_text(raw.get("date")) or None,
        stats={"downloads": _non_negative_int(raw.get("downloads")) or 0},
        metadata={
            "description": plain_text(raw.get("description")),
            "collection": "Prelinger Archives",
        },
    )


def normalize_detail(item: AssetItem, raw: Mapping[str, object]) -> AssetDetail:
    metadata = raw.get("metadata")
    values = metadata if isinstance(metadata, Mapping) else {}
    files = raw.get("files")
    candidates = (
        [
            resource
            for entry in files
            if isinstance(entry, Mapping)
            and (resource := _file_resource(item.id, entry)) is not None
        ]
        if isinstance(files, list)
        else []
    )
    candidates.sort(key=lambda resource: resource.size_bytes or 0)
    media: list[MediaResource] = []
    if candidates:
        playback_source = candidates[0]
        download_source = candidates[-1]
        media.append(replace(playback_source, role="playback"))
        media.append(replace(download_source, role="download"))
    duration = next(
        (resource.duration_seconds for resource in media if resource.duration_seconds),
        None,
    )
    rights = plain_text(values.get("rights")) or "请查看来源页面确认使用条件"
    verified = replace(
        item,
        title=plain_text(values.get("title")) or item.title,
        author=plain_text(values.get("creator")) or item.author,
        created_at=plain_text(values.get("date")) or item.created_at,
        duration_seconds=duration,
        metadata={
            **dict(item.metadata),
            "description": plain_text(values.get("description")),
            "rights": rights,
            "license_url": plain_text(values.get("licenseurl")),
            "collection": "Prelinger Archives",
        },
    )
    return AssetDetail(
        item=verified,
        images=(verified.preview_url,) if verified.preview_url else (),
        content=str(verified.metadata.get("description") or ""),
        metadata=verified.metadata,
        media=tuple(media),
    )


def _file_resource(identifier: str, raw: Mapping[str, object]) -> MediaResource | None:
    name = raw.get("name")
    file_format = plain_text(raw.get("format"))
    if (
        not isinstance(name, str)
        or not _SAFE_FILE.fullmatch(name)
        or not any(token in file_format.casefold() for token in ("mpeg4", "h.264"))
    ):
        return None
    return MediaResource(
        "video",
        f"https://archive.org/download/{quote(identifier, safe='')}/{quote(name, safe='')}",
        "video/mp4",
        "download",
        width=_positive_int(raw.get("width")),
        height=_positive_int(raw.get("height")),
        duration_seconds=_duration(raw.get("length")),
        size_bytes=_non_negative_int(raw.get("size")),
        label=file_format or "MP4",
    )


def _duration(value: object) -> int | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return max(0, round(value))
    if not isinstance(value, str):
        return None
    try:
        if ":" not in value:
            return max(0, round(float(value)))
        parts = [float(part) for part in value.split(":")]
        seconds = 0.0
        for part in parts:
            seconds = seconds * 60 + part
        return max(0, round(seconds))
    except ValueError:
        return None


def _positive_int(value: object) -> int | None:
    parsed = _non_negative_int(value)
    return parsed if parsed and parsed > 0 else None


def _non_negative_int(value: object) -> int | None:
    try:
        parsed = int(str(value))
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None
