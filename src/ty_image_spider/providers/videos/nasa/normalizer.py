"""NASA 视频搜索与资源清单的纯数据转换。"""

from __future__ import annotations

import re
from typing import Mapping, Sequence
from urllib.parse import quote, urlsplit, urlunsplit

from ....domain import AssetDetail, AssetItem, MediaResource
from ...collections.assets import plain_text


SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")


def normalize_search_item(raw: Mapping[str, object]) -> AssetItem | None:
    rows = _mappings(raw.get("data"))
    data = rows[0] if rows else None
    if data is None:
        return None
    nasa_id = plain_text(data.get("nasa_id"))
    if not SAFE_ID.fullmatch(nasa_id):
        return None
    manifest = raw.get("href")
    if not isinstance(manifest, str) or not _allowed_manifest(manifest):
        return None
    preview = next(
        (
            url
            for link in _mappings(raw.get("links"))
            if link.get("render") == "image"
            and isinstance(url := link.get("href"), str)
            and _allowed_asset(url, image=True)
        ),
        None,
    )
    if not isinstance(preview, str):
        return None
    author = plain_text(data.get("photographer")) or plain_text(
        data.get("secondary_creator")
    )
    return AssetItem(
        provider="nasa-video",
        id=nasa_id,
        kind="video",
        preview_url=preview,
        source_url="https://images.nasa.gov/details/" + quote(nasa_id, safe=""),
        title=plain_text(data.get("title")) or nasa_id,
        author=author or plain_text(data.get("center")) or None,
        created_at=plain_text(data.get("date_created")) or None,
        tags=tuple(_strings(data.get("keywords"))[:12]),
        metadata={
            "manifest_url": manifest,
            "description": plain_text(
                data.get("description") or data.get("description_508")
            ),
            "collection": "NASA Image and Video Library",
            "rights": "使用条件见 NASA 来源页面",
            "medium": f"NASA Video ID: {nasa_id}",
        },
    )


def normalize_detail(item: AssetItem, manifest: Sequence[str]) -> AssetDetail:
    ranked: list[tuple[int, str]] = []
    for url in manifest:
        normalized_url = _normalize_video_url(url)
        if normalized_url is None:
            continue
        name = urlsplit(normalized_url).path.casefold()
        if not name.endswith(".mp4"):
            continue
        rank = next(
            (
                score
                for marker, score in (
                    ("~orig.mp4", 4),
                    ("~large.mp4", 3),
                    ("~medium.mp4", 2),
                    ("~small.mp4", 1),
                )
                if name.endswith(marker)
            ),
            0,
        )
        ranked.append((rank, normalized_url))
    resources: list[MediaResource] = []
    if ranked:
        playback = min(ranked, key=lambda entry: abs(entry[0] - 2))
        download = max(ranked, key=lambda entry: entry[0])
        resources.append(
            MediaResource(
                "video", playback[1], "video/mp4", "playback", label="适中 MP4"
            )
        )
        resources.append(
            MediaResource(
                "video", download[1], "video/mp4", "download", label="最高质量 MP4"
            )
        )
    return AssetDetail(
        item,
        (item.preview_url,) if item.preview_url else (),
        content=str(item.metadata.get("description") or ""),
        metadata=item.metadata,
        media=tuple(resources),
    )


def _allowed_manifest(url: str) -> bool:
    return _allowed_asset(url, image=False) and urlsplit(url).path.endswith(
        "/collection.json"
    )


def _allowed_asset(url: str, *, image: bool) -> bool:
    try:
        parsed = urlsplit(url)
        suffixes = (
            (".jpg", ".jpeg", ".png", ".webp")
            if image
            else (
                ".json",
                ".mp4",
            )
        )
        return (
            parsed.scheme == "https"
            and parsed.hostname == "images-assets.nasa.gov"
            and parsed.port in {None, 443}
            and parsed.username is None
            and parsed.password is None
            and parsed.path.casefold().endswith(suffixes)
        )
    except ValueError:
        return False


def _normalize_video_url(url: str) -> str | None:
    try:
        parsed = urlsplit(url)
        if (
            parsed.scheme not in {"http", "https"}
            or parsed.hostname != "images-assets.nasa.gov"
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port
            not in ({None, 80} if parsed.scheme == "http" else {None, 443})
            or not parsed.path.casefold().endswith(".mp4")
        ):
            return None
        return urlunsplit(
            (
                "https",
                "images-assets.nasa.gov",
                parsed.path,
                parsed.query,
                "",
            )
        )
    except ValueError:
        return None


def _mappings(value: object) -> list[Mapping[str, object]]:
    return (
        [entry for entry in value if isinstance(entry, Mapping)]
        if isinstance(value, list)
        else []
    )


def _strings(value: object) -> list[str]:
    if isinstance(value, list):
        return [text for entry in value if (text := plain_text(entry))]
    text = plain_text(value)
    return [text] if text else []
