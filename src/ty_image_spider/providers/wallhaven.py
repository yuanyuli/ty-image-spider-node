"""Wallhaven 素材来源策略。"""

from __future__ import annotations

import json
import re
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping, Protocol

from ..cache import JsonCache
from ..models import (
    AssetDetail,
    AssetItem,
    DownloadResult,
    FilterField,
    FilterOption,
    JsonValue,
    ProviderCapabilities,
    ProviderDescriptor,
    ProviderStatus,
    SearchPage,
    SearchRequest,
    SpiderError,
)
from .wallhaven_client import WallhavenClient


_SAFE_ID = re.compile(r"^[a-z0-9]{6}$")
_CATEGORIES = {"all": "111", "general": "100", "anime": "010", "people": "001"}
_ORIENTATIONS = {
    "all": "",
    "landscape": "landscape",
    "portrait": "portrait",
    "square": "square",
}


class Downloader(Protocol):
    def download(self, url: str, item_id: str, output_root: Path) -> DownloadResult: ...


class WallhavenProvider:
    id = "wallhaven"

    def __init__(
        self, client: WallhavenClient, cache: JsonCache, downloader: Downloader
    ) -> None:
        self._client = client
        self._cache = cache
        self._downloader = downloader

    def descriptor(self) -> ProviderDescriptor:
        return ProviderDescriptor(
            id=self.id,
            label="Wallhaven",
            description="浏览 Wallhaven 的公开 SFW 壁纸与摄影素材",
            filters=(
                FilterField(
                    "category",
                    "分类",
                    "select",
                    "all",
                    tuple(
                        FilterOption(value, label)
                        for value, label in (
                            ("all", "全部"),
                            ("general", "综合"),
                            ("anime", "动漫"),
                            ("people", "人物"),
                        )
                    ),
                ),
                FilterField(
                    "sorting",
                    "排序",
                    "select",
                    "relevance",
                    tuple(
                        FilterOption(value, label)
                        for value, label in (
                            ("relevance", "相关度"),
                            ("date_added", "最新"),
                            ("views", "浏览量"),
                            ("favorites", "收藏量"),
                            ("toplist", "热门榜"),
                        )
                    ),
                ),
                FilterField(
                    "top_range",
                    "榜单范围",
                    "select",
                    "1M",
                    tuple(
                        FilterOption(value, label)
                        for value, label in (
                            ("1d", "一天"),
                            ("1w", "一周"),
                            ("1M", "一月"),
                            ("3M", "三月"),
                            ("1y", "一年"),
                        )
                    ),
                ),
                FilterField(
                    "orientation",
                    "方向",
                    "select",
                    "all",
                    tuple(
                        FilterOption(value, label)
                        for value, label in (
                            ("all", "不限"),
                            ("landscape", "横向"),
                            ("portrait", "纵向"),
                            ("square", "方形"),
                        )
                    ),
                ),
                FilterField(
                    "atleast",
                    "最低分辨率",
                    "select",
                    "",
                    tuple(
                        FilterOption(value, label)
                        for value, label in (
                            ("", "不限"),
                            ("1920x1080", "1920 x 1080"),
                            ("2560x1440", "2560 x 1440"),
                            ("3840x2160", "3840 x 2160"),
                        )
                    ),
                ),
            ),
            capabilities=ProviderCapabilities(bulk_download=True, pagination="page"),
        )

    def status(self) -> ProviderStatus:
        return ProviderStatus(True, message="公开 SFW API")

    def search(self, request: SearchRequest) -> SearchPage:
        params = _search_parameters(request)
        cache_key = "wallhaven:" + json.dumps(
            params, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        try:
            raw_page = self._client.search(params)
            next_cursor = (
                str(raw_page.current_page + 1)
                if raw_page.current_page < raw_page.last_page
                else None
            )
            page = SearchPage(
                tuple(_normalize(raw) for raw in raw_page.items), next_cursor
            )
            self._cache.put(cache_key, page.to_dict())
            return page
        except SpiderError:
            cached = self._cache.get(cache_key, max_age_seconds=None)
            if cached is None:
                raise
            return _cached_page(cached)

    def detail(self, item: AssetItem) -> AssetDetail:
        _require_item(item)
        updated = self._verified_detail(item.id)
        image_url = _download_url(updated)
        return AssetDetail(
            replace(updated, preview_url=item.preview_url or updated.preview_url),
            (image_url,),
            metadata=updated.metadata,
        )

    def download(self, item: AssetItem, output_root: Path) -> DownloadResult:
        _require_item(item)
        verified = self._verified_detail(item.id)
        return self._downloader.download(
            _download_url(verified), verified.id, output_root
        )

    def _verified_detail(self, item_id: str) -> AssetItem:
        verified = _normalize(self._client.detail(item_id))
        if verified.id != item_id:
            raise SpiderError(
                "wallhaven_invalid_response", "Wallhaven 详情 ID 不匹配", status=502
            )
        return verified


def _search_parameters(request: SearchRequest) -> dict[str, object]:
    filters = request.filters
    category = str(filters.get("category") or "all")
    sorting = str(filters.get("sorting") or "relevance")
    if not request.query.strip() and sorting == "relevance":
        sorting = "date_added"
    orientation = str(filters.get("orientation") or "all")
    page = _page_number(request.cursor)
    params: dict[str, object] = {
        "q": request.query.strip(),
        "categories": _CATEGORIES.get(category, "111"),
        "purity": "100",
        "sorting": sorting
        if sorting in {"relevance", "date_added", "views", "favorites", "toplist"}
        else "relevance",
        "order": "desc",
        "topRange": str(filters.get("top_range") or "1M")
        if sorting == "toplist"
        else None,
        "ratios": _ORIENTATIONS.get(orientation, ""),
        "atleast": str(filters.get("atleast") or ""),
        "page": page,
    }
    return {key: value for key, value in params.items() if value not in (None, "")}


def _page_number(cursor: str | None) -> int:
    if cursor is None:
        return 1
    try:
        page = int(cursor)
    except ValueError:
        return 1
    return max(1, page)


def _normalize(raw: Mapping[str, Any]) -> AssetItem:
    item_id = str(raw.get("id") or "")
    if not _SAFE_ID.fullmatch(item_id) or str(raw.get("purity") or "") != "sfw":
        raise SpiderError(
            "wallhaven_invalid_response", "Wallhaven 返回了无效素材", status=502
        )
    raw_thumbs = raw.get("thumbs")
    thumbs: Mapping[str, Any] = raw_thumbs if isinstance(raw_thumbs, Mapping) else {}
    raw_uploader = raw.get("uploader")
    uploader: Mapping[str, Any] = (
        raw_uploader if isinstance(raw_uploader, Mapping) else {}
    )
    tags_value = raw.get("tags")
    raw_tags: list[Any] = tags_value if isinstance(tags_value, list) else []
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
        "file_size": _integer_or_none(raw.get("file_size")),
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
        width=_integer_or_none(raw.get("dimension_x")),
        height=_integer_or_none(raw.get("dimension_y")),
        stats={
            "views": _integer_or_zero(raw.get("views")),
            "favorites": _integer_or_zero(raw.get("favorites")),
        },
        tags=tags,
        metadata=metadata,
    )


def _download_url(item: AssetItem) -> str:
    value = item.metadata.get("download_url")
    if not isinstance(value, str) or not value:
        raise SpiderError("missing_image_url", "Wallhaven 素材缺少原图地址")
    return value


def _require_item(item: AssetItem) -> None:
    if item.provider != "wallhaven" or not _SAFE_ID.fullmatch(item.id):
        raise SpiderError("invalid_asset", "Wallhaven 素材数据无效")


def _cached_page(value: object) -> SearchPage:
    if not isinstance(value, Mapping) or not isinstance(value.get("items"), list):
        raise SpiderError("cache_invalid", "Wallhaven 缓存数据无效", status=502)
    cursor = value.get("next_cursor")
    return SearchPage(
        tuple(AssetItem.from_untrusted(item) for item in value["items"]),
        str(cursor) if cursor else None,
        stale=True,
        message="正在显示缓存结果",
    )


def _integer_or_none(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _integer_or_zero(value: object) -> int:
    normalized = _integer_or_none(value)
    return normalized if normalized is not None else 0
