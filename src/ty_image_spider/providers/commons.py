"""Wikimedia Commons 精选图片来源。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from ..cache import JsonCache
from ..models import (
    AssetDetail,
    AssetItem,
    DownloadResult,
    FilterField,
    FilterOption,
    ProviderCapabilities,
    ProviderDescriptor,
    ProviderPresentation,
    ProviderStatus,
    SearchPage,
    SearchRequest,
    SpiderError,
)
from ..network_retry import retry_call
from ..security import read_limited, require_https_host
from ..version import USER_AGENT
from .download_policy import HostDownloadPolicy
from .museum_assets import plain_text


_API = "https://commons.wikimedia.org/w/api.php"
_SAFE_ID = re.compile(r"^[1-9][0-9]*$")
_CATEGORIES = {
    "featured": ("精选图片", "Category:Featured pictures on Wikimedia Commons"),
    "quality": ("优质图片", "Category:Quality images"),
    "photography": (
        "精选摄影",
        "Category:Featured photographs in the public domain",
    ),
    "art": ("艺术作品", "Category:Quality images of works of art"),
}

IMAGE_POLICY = HostDownloadPolicy(
    "commons",
    lambda host: host == "upload.wikimedia.org",
    id_pattern=r"[1-9][0-9]*",
)
_PREVIEW_POLICY = HostDownloadPolicy(
    "commons-preview",
    lambda host: host in {"upload.wikimedia.org", "thumb.wikimedia.org"},
)
_SUPPORTED_IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp")


class Downloader(Protocol):
    def download(self, url: str, item_id: str, output_root: Path) -> DownloadResult: ...


@dataclass(frozen=True, slots=True)
class CommonsPage:
    items: tuple[Mapping[str, Any], ...]
    next_cursor: str | None = None


class CommonsClient:
    def __init__(
        self,
        cache: JsonCache | None = None,
        open_url: Callable[..., Any] = urlopen,
    ) -> None:
        self._cache = cache
        self._open_url = open_url

    def search(self, query: str, category: str, cursor: str | None) -> CommonsPage:
        if category not in _CATEGORIES:
            raise SpiderError("invalid_category", "Commons 分类无效")
        params: dict[str, object] = {
            "action": "query",
            "format": "json",
            "formatversion": 2,
            "prop": "imageinfo",
            "iiprop": "url|size|extmetadata",
            "iiurlwidth": 800,
        }
        if query:
            params.update(
                generator="search",
                gsrsearch=f"{query} incategory:{_CATEGORIES[category][1][9:]}",
                gsrnamespace=6,
                gsrlimit=24,
            )
            if cursor:
                if not cursor.startswith("s:") or not cursor[2:].isdigit():
                    raise SpiderError("invalid_cursor", "Commons 分页游标无效")
                params["gsroffset"] = cursor[2:]
        else:
            params.update(
                generator="categorymembers",
                gcmtitle=_CATEGORIES[category][1],
                gcmtype="file",
                gcmlimit=24,
            )
            if cursor:
                if not cursor.startswith("g:") or len(cursor) > 2048:
                    raise SpiderError("invalid_cursor", "Commons 分页游标无效")
                params["gcmcontinue"] = cursor[2:]
        data = self._get(params)
        query_data = data.get("query")
        pages = query_data.get("pages") if isinstance(query_data, Mapping) else []
        rows = (
            tuple(row for row in pages if isinstance(row, Mapping))
            if isinstance(pages, list)
            else ()
        )
        continuation = data.get("continue")
        next_cursor = None
        if isinstance(continuation, Mapping):
            if isinstance(continuation.get("gsroffset"), int):
                next_cursor = f"s:{continuation['gsroffset']}"
            elif isinstance(continuation.get("gcmcontinue"), str):
                next_cursor = "g:" + continuation["gcmcontinue"]
        return CommonsPage(rows, next_cursor)

    def file(self, page_id: int) -> Mapping[str, Any]:
        if page_id < 1:
            raise SpiderError("invalid_asset", "Commons 素材 ID 无效")
        data = self._get(
            {
                "action": "query",
                "format": "json",
                "formatversion": 2,
                "pageids": page_id,
                "prop": "imageinfo",
                "iiprop": "url|size|extmetadata",
                "iiurlwidth": 800,
            }
        )
        query_data = data.get("query")
        pages = query_data.get("pages") if isinstance(query_data, Mapping) else []
        if (
            not isinstance(pages, list)
            or not pages
            or not isinstance(pages[0], Mapping)
        ):
            raise SpiderError("commons_not_found", "Commons 图片不存在", status=404)
        return pages[0]

    def _get(self, params: Mapping[str, object]) -> Mapping[str, Any]:
        url = _API + "?" + urlencode(sorted(params.items()))
        cached = self._cache.get(url, 300) if self._cache else None
        if isinstance(cached, Mapping):
            return cached
        request = Request(
            url,
            headers={"Accept": "application/json", "User-Agent": USER_AGENT},
        )

        def fetch() -> Mapping[str, Any]:
            with self._open_url(request, timeout=30) as response:
                require_https_host(
                    response.geturl(), lambda host: host == "commons.wikimedia.org"
                )
                data = json.loads(read_limited(response, 12 * 1024 * 1024))
            if not isinstance(data, Mapping):
                raise ValueError("invalid root")
            return data

        try:
            data = retry_call(fetch)
        except HTTPError as exc:
            raise SpiderError(
                "commons_http_error",
                f"Commons 请求失败（{exc.code}）",
                status=502,
            ) from exc
        except (URLError, TimeoutError, OSError, ValueError, UnicodeError) as exc:
            raise SpiderError(
                "commons_unavailable",
                "Wikimedia Commons 暂时不可用",
                status=502,
            ) from exc
        if self._cache:
            self._cache.put(url, dict(data))
        return data


class CommonsProvider:
    id = "commons"
    image_policy = IMAGE_POLICY

    def __init__(self, client: CommonsClient, downloader: Downloader) -> None:
        self._client = client
        self._downloader = downloader

    def descriptor(self) -> ProviderDescriptor:
        return ProviderDescriptor(
            presentation=ProviderPresentation(
                "collections",
                "艺术馆藏",
                "WMC",
                "WIKIMEDIA COMMONS",
                30,
                60,
                "按当前条件新增最多100张精选图片，已有缓存将跳过",
                True,
            ),
            id=self.id,
            label="Wikimedia Commons",
            description="浏览 Wikimedia Commons 精选、优质和开放许可图片",
            filters=(
                FilterField(
                    "category",
                    "图片分类",
                    "select",
                    "featured",
                    tuple(
                        FilterOption(key, value[0])
                        for key, value in _CATEGORIES.items()
                    ),
                ),
            ),
            capabilities=ProviderCapabilities(
                bulk_download=True, pagination="cursor", cache=True
            ),
            search_placeholder="可留空浏览精选图片；支持中英文关键词",
        )

    def status(self) -> ProviderStatus:
        return ProviderStatus(True, message="开放许可精选图片")

    def search(self, request: SearchRequest) -> SearchPage:
        category = str(request.filters.get("category") or "featured")
        if category not in _CATEGORIES:
            raise SpiderError("invalid_category", "Commons 分类无效")
        raw = self._client.search(request.query.strip(), category, request.cursor)
        return SearchPage(
            tuple(item for row in raw.items if (item := _normalize(row)) is not None),
            raw.next_cursor,
        )

    def detail(self, item: AssetItem) -> AssetDetail:
        _require_item(item)
        verified = _normalize(self._client.file(int(item.id)))
        if verified is None or verified.id != item.id:
            raise SpiderError(
                "commons_invalid_response", "Commons 图片详情无效", status=502
            )
        original = str(verified.metadata["original_url"])
        return AssetDetail(
            verified,
            (original,),
            content=str(verified.metadata.get("description") or ""),
            metadata=verified.metadata,
        )

    def download(self, item: AssetItem, output_root: Path) -> DownloadResult:
        verified = self.detail(item).item
        return self._downloader.download(
            str(verified.metadata["original_url"]), verified.id, output_root
        )


def _normalize(raw: Mapping[str, Any]) -> AssetItem | None:
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
            "attribution_required": (
                _meta(values, "AttributionRequired").casefold() == "true"
            ),
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


def _require_item(item: AssetItem) -> None:
    if item.provider != "commons" or not _SAFE_ID.fullmatch(item.id):
        raise SpiderError("invalid_asset", "Commons 素材数据无效")
