"""WallpapersCraft 壁纸来源。"""

from __future__ import annotations

import json
import re
from dataclasses import replace
from pathlib import Path
from typing import Mapping, Protocol

from ....infrastructure.cache import JsonCache
from ....domain import (
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
from ...shared import HostDownloadPolicy
from .client import WallpapersCraftClient
from .parser import parse_list, parse_original


_ROOT = "https://wallpaperscraft.com"
_MAX_HTML_BYTES = 8 * 1024 * 1024
_SAFE_PATH = re.compile(r"^/download/[a-z0-9_-]+_([0-9]+)/([0-9]+x[0-9]+)$")
_SAFE_ID = re.compile(r"^[0-9]+-[0-9]+x[0-9]+$")
_CATEGORIES = {
    "nature": "自然",
    "city": "城市",
    "abstract": "抽象",
    "space": "太空",
    "anime": "动漫",
    "animals": "动物",
    "cars": "汽车",
    "minimalism": "极简",
}
_RESOLUTIONS = ("1920x1080", "2560x1440", "3840x2160", "3440x1440")

IMAGE_POLICY = HostDownloadPolicy(
    "wallpaperscraft",
    lambda host: host == "images.wallpaperscraft.com",
    id_pattern=r"[0-9]+-[0-9]+x[0-9]+",
)


class Downloader(Protocol):
    def download(self, url: str, item_id: str, output_root: Path) -> DownloadResult: ...


class WallpapersCraftProvider:
    id = "wallpaperscraft"
    image_policy = IMAGE_POLICY

    def __init__(
        self,
        client: WallpapersCraftClient,
        cache: JsonCache,
        downloader: Downloader,
    ) -> None:
        self._client = client
        self._cache = cache
        self._downloader = downloader

    def descriptor(self) -> ProviderDescriptor:
        return ProviderDescriptor(
            presentation=ProviderPresentation(
                "wallpaper",
                "壁纸",
                "WC",
                "WALLPAPERSCRAFT",
                15,
                40,
                "按当前分类新增最多100张素材，已有缓存将跳过",
                True,
            ),
            id=self.id,
            label="WallpapersCraft",
            description="浏览 WallpapersCraft 公开桌面壁纸",
            filters=(
                FilterField(
                    "category",
                    "分类",
                    "select",
                    "nature",
                    tuple(
                        FilterOption(key, label) for key, label in _CATEGORIES.items()
                    ),
                ),
                FilterField(
                    "resolution",
                    "分辨率",
                    "select",
                    "1920x1080",
                    tuple(FilterOption(value, value) for value in _RESOLUTIONS),
                ),
            ),
            capabilities=ProviderCapabilities(
                bulk_download=True, pagination="page", cache=True
            ),
            search_placeholder="可留空浏览分类；关键词建议使用英文",
        )

    def status(self) -> ProviderStatus:
        return ProviderStatus(True, message="公开壁纸目录")

    def search(self, request: SearchRequest) -> SearchPage:
        category = str(request.filters.get("category") or "nature")
        resolution = str(request.filters.get("resolution") or "1920x1080")
        if category not in _CATEGORIES:
            category = "nature"
        if resolution not in _RESOLUTIONS:
            resolution = "1920x1080"
        page_number = _page_number(request.cursor)
        query = request.query.strip()
        cache_key = "wallpaperscraft:" + json.dumps(
            {
                "category": category,
                "resolution": resolution,
                "query": query,
                "page": page_number,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        try:
            raw = self._client.list(category, resolution, query, page_number)
            page = SearchPage(
                tuple(parse_list(raw.html)),
                str(page_number + 1) if page_number < raw.last_page else None,
            )
            self._cache.put(cache_key, page.to_dict())
            return page
        except SpiderError:
            cached = self._cache.get(cache_key, max_age_seconds=None)
            if not isinstance(cached, Mapping) or not isinstance(
                cached.get("items"), list
            ):
                raise
            cursor = cached.get("next_cursor")
            return SearchPage(
                tuple(AssetItem.from_untrusted(item) for item in cached["items"]),
                str(cursor) if cursor else None,
                stale=True,
                message="正在显示缓存结果",
            )

    def detail(self, item: AssetItem) -> AssetDetail:
        _require_item(item)
        path = item.metadata.get("detail_path")
        if not isinstance(path, str) or not _SAFE_PATH.fullmatch(path):
            raise SpiderError("invalid_asset", "WallpapersCraft 详情地址无效")
        original = parse_original(self._client.detail(path), item)
        metadata = {**item.metadata, "original_url": original}
        enriched = replace(item, metadata=metadata)
        return AssetDetail(enriched, (original,), metadata=metadata)

    def download(self, item: AssetItem, output_root: Path) -> DownloadResult:
        verified = self.detail(item).item
        return self._downloader.download(
            str(verified.metadata["original_url"]), verified.id, output_root
        )


def _page_number(cursor: str | None) -> int:
    try:
        return max(1, int(cursor or 1))
    except ValueError:
        return 1


def _require_item(item: AssetItem) -> None:
    if item.provider != "wallpaperscraft" or not _SAFE_ID.fullmatch(item.id):
        raise SpiderError("invalid_asset", "WallpapersCraft 素材数据无效")
