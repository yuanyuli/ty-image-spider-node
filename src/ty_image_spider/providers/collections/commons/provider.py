"""Wikimedia Commons 精选图片来源。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Protocol

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
from .client import CATEGORIES, CommonsClient
from .normalizer import IMAGE_POLICY, normalize_file


_SAFE_ID = re.compile(r"^[1-9][0-9]*$")


class Downloader(Protocol):
    def download(self, url: str, item_id: str, output_root: Path) -> DownloadResult: ...


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
                        FilterOption(key, value[0]) for key, value in CATEGORIES.items()
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
        if category not in CATEGORIES:
            raise SpiderError("invalid_category", "Commons 分类无效")
        raw = self._client.search(request.query.strip(), category, request.cursor)
        return SearchPage(
            tuple(
                item for row in raw.items if (item := normalize_file(row)) is not None
            ),
            raw.next_cursor,
        )

    def detail(self, item: AssetItem) -> AssetDetail:
        _require_item(item)
        verified = normalize_file(self._client.file(int(item.id)))
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


def _require_item(item: AssetItem) -> None:
    if item.provider != "commons" or not _SAFE_ID.fullmatch(item.id):
        raise SpiderError("invalid_asset", "Commons 素材数据无效")
