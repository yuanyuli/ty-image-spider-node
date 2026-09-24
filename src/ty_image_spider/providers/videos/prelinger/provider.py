"""Prelinger Archives 视频 Provider 编排。"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from ....domain import (
    AssetDetail,
    AssetItem,
    DownloadResult,
    FilterField,
    FilterOption,
    MediaResource,
    ProviderCapabilities,
    ProviderDescriptor,
    ProviderPresentation,
    ProviderStatus,
    SearchPage,
    SearchRequest,
    SpiderError,
)
from ...shared import HostDownloadPolicy
from .client import PrelingerClient
from .normalizer import SAFE_IDENTIFIER, normalize_detail, normalize_search_item


IMAGE_POLICY = HostDownloadPolicy(
    "prelinger",
    lambda host: host == "archive.org",
    id_pattern=SAFE_IDENTIFIER.pattern,
)


class Downloader(Protocol):
    def download(
        self, resource: MediaResource, item_id: str, output_root: Path
    ) -> DownloadResult: ...


class PrelingerProvider:
    id = "prelinger"
    image_policy = IMAGE_POLICY

    def __init__(self, client: PrelingerClient, downloader: Downloader) -> None:
        self._client = client
        self._downloader = downloader

    def descriptor(self) -> ProviderDescriptor:
        return ProviderDescriptor(
            id=self.id,
            label="Prelinger Archives",
            presentation=ProviderPresentation(
                "videos",
                "视频素材",
                "PRE",
                "PRELINGER ARCHIVES",
                60,
                10,
                "按当前条件新增最多100条封面与资料；视频按需播放和下载",
            ),
            description="浏览 Internet Archive 的经典广告、工业与文化影片",
            filters=(
                FilterField(
                    "sort",
                    "排序",
                    "select",
                    "popular",
                    (
                        FilterOption("popular", "热门"),
                        FilterOption("newest", "最新"),
                        FilterOption("oldest", "最早"),
                        FilterOption("relevance", "相关"),
                    ),
                ),
            ),
            capabilities=ProviderCapabilities(
                bulk_download=False, pagination="page", cache=True
            ),
            search_placeholder="输入英文主题，如 design、travel、industry",
        )

    def status(self) -> ProviderStatus:
        return ProviderStatus(True, message="无需账号，可浏览开放档案视频")

    def search(self, request: SearchRequest) -> SearchPage:
        page = _page(request.cursor)
        sort = str(request.filters.get("sort") or "popular")
        raw = self._client.search(request.query.strip(), page, sort, request.refresh)
        response = raw.get("response")
        if not isinstance(response, dict):
            raise SpiderError("prelinger_invalid_response", "Prelinger 搜索结果无效")
        docs = response.get("docs")
        rows = docs if isinstance(docs, list) else []
        items = tuple(
            item
            for row in rows
            if isinstance(row, dict)
            and (item := normalize_search_item(row)) is not None
        )
        total = response.get("numFound")
        has_next = isinstance(total, int) and page * 24 < total
        return SearchPage(items, str(page + 1) if has_next else None)

    def detail(self, item: AssetItem) -> AssetDetail:
        self._require_item(item)
        return normalize_detail(
            item, self._client.metadata(item.id, refresh=False)
        )

    def download(self, item: AssetItem, output_root: Path) -> DownloadResult:
        detail = self.detail(item)
        resource = next(
            (entry for entry in detail.media if entry.role == "download"),
            next(iter(detail.media), None),
        )
        if resource is None:
            raise SpiderError("video_unavailable", "当前视频没有可下载文件", status=404)
        return self._downloader.download(resource, item.id, output_root)

    @staticmethod
    def _require_item(item: AssetItem) -> None:
        if item.provider != "prelinger" or not SAFE_IDENTIFIER.fullmatch(item.id):
            raise SpiderError("invalid_asset", "Prelinger 素材数据无效")


def _page(cursor: str | None) -> int:
    if cursor is None:
        return 1
    if not cursor.isdigit() or int(cursor) < 1:
        raise SpiderError("invalid_cursor", "Prelinger 分页游标无效")
    return int(cursor)
