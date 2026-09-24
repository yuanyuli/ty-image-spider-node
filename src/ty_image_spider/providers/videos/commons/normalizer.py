"""Commons 视频响应到稳定领域模型的纯转换。"""

from __future__ import annotations

from typing import Mapping
from urllib.parse import urlsplit

from ....domain import AssetDetail, AssetItem, MediaResource
from ...collections.assets import plain_text


def normalize_search_item(raw: Mapping[str, object]) -> AssetItem | None:
    page_id = raw.get("pageid")
    title = raw.get("title")
    info = _video_info(raw)
    if (
        not isinstance(page_id, int)
        or page_id < 1
        or not isinstance(title, str)
        or not title.startswith("File:")
        or info is None
    ):
        return None
    preview = info.get("thumburl")
    if not isinstance(preview, str) or not _allowed_upload_url(preview):
        return None
    metadata = _metadata(info)
    return AssetItem(
        provider="commons-video",
        id=str(page_id),
        kind="video",
        preview_url=preview,
        source_url=_string(info.get("descriptionurl")),
        title=_meta(metadata, "ObjectName") or plain_text(title).removeprefix("File:"),
        author=_meta(metadata, "Artist") or None,
        created_at=_meta(metadata, "DateTimeOriginal") or None,
        width=_positive_int(info.get("width")),
        height=_positive_int(info.get("height")),
        duration_seconds=_duration(info.get("duration")),
        metadata={
            "file_title": title,
            "description": _meta(metadata, "ImageDescription"),
            "rights": _meta(metadata, "LicenseShortName")
            or "请查看来源页面确认使用条件",
            "license_url": _meta(metadata, "LicenseUrl"),
            "attribution_required": _meta(
                metadata, "AttributionRequired"
            ).casefold()
            == "true",
            "collection": "Wikimedia Commons",
        },
    )


def normalize_detail(item: AssetItem, raw: Mapping[str, object]) -> AssetDetail:
    page = _first_page(raw)
    info = _video_info(page) if page is not None else None
    if info is None:
        return AssetDetail(item, (item.preview_url,) if item.preview_url else ())
    verified = normalize_search_item(page)
    if verified is None or verified.id != item.id:
        verified = item
    resources: list[MediaResource] = []
    playback = _select_playback(info)
    if playback is not None:
        resources.append(playback)
    original = _original_resource(info)
    if original is not None:
        resources.append(original)
    return AssetDetail(
        verified,
        (verified.preview_url,) if verified.preview_url else (),
        content=str(verified.metadata.get("description") or ""),
        metadata=verified.metadata,
        media=tuple(resources),
    )


def _select_playback(info: Mapping[str, object]) -> MediaResource | None:
    derivatives = info.get("derivatives")
    if not isinstance(derivatives, list):
        return None
    candidates: list[tuple[int, int, MediaResource]] = []
    for raw in derivatives:
        if not isinstance(raw, Mapping):
            continue
        url = raw.get("src")
        mime = _string(raw.get("type")).split(";", 1)[0].strip().casefold()
        if (
            not isinstance(url, str)
            or not _allowed_upload_url(url)
            or mime not in {"video/mp4", "video/webm", "video/ogg"}
        ):
            continue
        width = _positive_int(raw.get("width"))
        resource = MediaResource(
            "video",
            url,
            mime,
            "playback",
            width=width,
            height=_positive_int(raw.get("height")),
            duration_seconds=_duration(info.get("duration")),
            label=plain_text(raw.get("title")) or mime.removeprefix("video/").upper(),
        )
        candidates.append((0 if mime == "video/mp4" else 1, abs((width or 720) - 1280), resource))
    return min(candidates, default=(0, 0, None), key=lambda entry: (entry[0], entry[1]))[2]


def _original_resource(info: Mapping[str, object]) -> MediaResource | None:
    url = info.get("url")
    if not isinstance(url, str) or not _allowed_upload_url(url):
        return None
    suffix = urlsplit(url).path.casefold()
    mime = "video/webm" if suffix.endswith(".webm") else "video/ogg" if suffix.endswith((".ogv", ".ogg")) else "video/mp4" if suffix.endswith(".mp4") else ""
    if not mime:
        return None
    return MediaResource(
        "video",
        url,
        mime,
        "download",
        width=_positive_int(info.get("width")),
        height=_positive_int(info.get("height")),
        duration_seconds=_duration(info.get("duration")),
        size_bytes=_positive_int(info.get("size")),
        label="原始文件",
    )


def _first_page(raw: Mapping[str, object]) -> Mapping[str, object] | None:
    query = raw.get("query")
    pages = query.get("pages") if isinstance(query, Mapping) else None
    if isinstance(pages, list) and pages and isinstance(pages[0], Mapping):
        return pages[0]
    return None


def _video_info(raw: Mapping[str, object]) -> Mapping[str, object] | None:
    infos = raw.get("videoinfo")
    if isinstance(infos, list) and infos and isinstance(infos[0], Mapping):
        return infos[0]
    return None


def _metadata(info: Mapping[str, object]) -> Mapping[str, object]:
    value = info.get("extmetadata")
    return value if isinstance(value, Mapping) else {}


def _meta(values: Mapping[str, object], name: str) -> str:
    entry = values.get(name)
    return plain_text(entry.get("value")) if isinstance(entry, Mapping) else ""


def _allowed_upload_url(url: str) -> bool:
    try:
        parsed = urlsplit(url)
        return (
            parsed.scheme == "https"
            and parsed.hostname == "upload.wikimedia.org"
            and parsed.username is None
            and parsed.password is None
            and parsed.port in {None, 443}
        )
    except ValueError:
        return False


def _duration(value: object) -> int | None:
    try:
        number = float(str(value))
    except (TypeError, ValueError):
        return None
    return max(0, round(number))


def _positive_int(value: object) -> int | None:
    try:
        number = int(str(value))
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _string(value: object) -> str:
    return value if isinstance(value, str) else ""
