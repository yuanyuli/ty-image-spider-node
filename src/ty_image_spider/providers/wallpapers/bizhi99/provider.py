"""壁纸网（bizhi99.com）来源。"""

from __future__ import annotations

import json
import re
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
from .client import Bizhi99Client
from .parser import parse_detail, parse_list


_ROOT = "https://www.bizhi99.com"
_IMAGE_ROOT = "https://pic.bizhi66.com"
_SAFE_ID = re.compile(r"^[0-9]+$")
_CATEGORY_PATHS = {
    "latest": ("/zuixin/", "最新"),
    "landscape": ("/c2/", "风景美图"),
    "stars": ("/c18/", "星空壁纸"),
    "anime": ("/c3/", "动漫壁纸"),
    "background": ("/c21/", "背景壁纸"),
    "animal": ("/c4/", "萌宠动物"),
    "car": ("/c5/", "汽车天下"),
    "movie": ("/s/1842/", "影视剧照"),
    "ultrawide": ("/3440x1440/", "带鱼屏"),
    "4k": ("/3840x2160/", "4K壁纸"),
}

IMAGE_POLICY = HostDownloadPolicy(
    "bizhi99", lambda host: host == "pic.bizhi66.com", id_pattern=r"[0-9]+"
)


class Downloader(Protocol):
    def download(self, url: str, item_id: str, output_root: Path) -> DownloadResult: ...


class Bizhi99Provider:
    id = "bizhi99"
    image_policy = IMAGE_POLICY

    def __init__(
        self, client: Bizhi99Client, cache: JsonCache, downloader: Downloader
    ) -> None:
        self._client = client
        self._cache = cache
        self._downloader = downloader

    def descriptor(self) -> ProviderDescriptor:
        return ProviderDescriptor(
            presentation=ProviderPresentation(
                "wallpaper",
                "壁纸",
                "B",
                "BIZHI99",
                15,
                30,
                "按当前分类新增最多100张素材，已有缓存将跳过",
                True,
            ),
            id=self.id,
            label="壁纸网",
            description="浏览壁纸网公开的中文 4K、5K 和带鱼屏壁纸",
            filters=(
                FilterField(
                    "category",
                    "分类",
                    "select",
                    "latest",
                    tuple(
                        FilterOption(value, label)
                        for value, (_, label) in _CATEGORY_PATHS.items()
                    ),
                ),
            ),
            capabilities=ProviderCapabilities(
                bulk_download=True, pagination="page", cache=True
            ),
            search_placeholder="按标题筛选，例如：风景、电影、动漫",
        )

    def status(self) -> ProviderStatus:
        return ProviderStatus(True, message="公开 HTML 壁纸目录")

    def search(self, request: SearchRequest) -> SearchPage:
        category = str(request.filters.get("category") or "latest")
        path = _CATEGORY_PATHS.get(category, _CATEGORY_PATHS["latest"])[0]
        page_number = _page_number(request.cursor)
        params = {
            "category": category,
            "query": request.query.strip(),
            "page": page_number,
        }
        cache_key = "bizhi99:" + json.dumps(
            params, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        try:
            raw = self._client.list(path, page_number)
            items = tuple(parse_list(raw.html, request.query.strip()))
            next_cursor = str(page_number + 1) if page_number < raw.last_page else None
            page = SearchPage(items, next_cursor)
            self._cache.put(cache_key, page.to_dict())
            return page
        except SpiderError:
            cached = self._cache.get(cache_key, max_age_seconds=None)
            if cached is None:
                raise
            return _cached_page(cached)

    def detail(self, item: AssetItem) -> AssetDetail:
        _require_item(item)
        parsed = parse_detail(self._client.detail(item.id), item)
        return AssetDetail(
            parsed, (str(parsed.metadata["original_url"]),), metadata=parsed.metadata
        )

    def download(self, item: AssetItem, output_root: Path) -> DownloadResult:
        _require_item(item)
        verified = self.detail(item).item
        return self._downloader.download(
            str(verified.metadata["original_url"]), verified.id, output_root
        )


def _page_number(cursor: str | None) -> int:
    try:
        return max(1, int(cursor or 1))
    except ValueError:
        return 1


def _cached_page(value: object) -> SearchPage:
    if not isinstance(value, Mapping) or not isinstance(value.get("items"), list):
        raise SpiderError("cache_invalid", "壁纸网缓存数据无效", status=502)
    cursor = value.get("next_cursor")
    return SearchPage(
        tuple(AssetItem.from_untrusted(item) for item in value["items"]),
        str(cursor) if cursor else None,
        stale=True,
        message="正在显示缓存结果",
    )


def _require_item(item: AssetItem) -> None:
    if item.provider != "bizhi99" or not _SAFE_ID.fullmatch(item.id):
        raise SpiderError("invalid_asset", "壁纸网素材数据无效")
