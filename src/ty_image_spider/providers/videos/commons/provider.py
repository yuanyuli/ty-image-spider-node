"""Wikimedia Commons 视频 Provider 编排。"""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Protocol

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
from .client import CATEGORIES, CommonsVideoClient
from .normalizer import normalize_detail, normalize_search_item


IMAGE_POLICY = HostDownloadPolicy(
    "commons-video",
    lambda host: host == "upload.wikimedia.org",
    id_pattern=r"[1-9][0-9]*",
)


class Downloader(Protocol):
    def download(
        self, resource: MediaResource, item_id: str, output_root: Path
    ) -> DownloadResult: ...


class CommonsVideoProvider:
    id = "commons-video"
    image_policy = IMAGE_POLICY

    def __init__(self, client: CommonsVideoClient, downloader: Downloader) -> None:
        self._client = client
        self._downloader = downloader

    def descriptor(self) -> ProviderDescriptor:
        labels = {
            "all": "全部视频",
            "film": "电影",
            "animation": "动画",
            "science": "科学",
            "nature": "自然",
        }
        return ProviderDescriptor(
            id=self.id,
            label="Wikimedia Commons 视频",
            presentation=ProviderPresentation(
                "videos",
                "视频素材",
                "WMC",
                "WIKIMEDIA COMMONS VIDEO",
                35,
                20,
                "按当前条件新增最多100条封面与资料；视频按需播放和下载",
            ),
            description="搜索 Wikimedia Commons 的开放许可视频",
            filters=(
                FilterField(
                    "category",
                    "视频分类",
                    "select",
                    "all",
                    tuple(FilterOption(key, labels[key]) for key in CATEGORIES),
                ),
            ),
            capabilities=ProviderCapabilities(
                bulk_download=False, pagination="cursor", cache=True
            ),
            search_placeholder="支持中文或英文关键词",
        )

    def status(self) -> ProviderStatus:
        return ProviderStatus(True, message="开放许可视频，使用条件以单项详情为准")

    def search(self, request: SearchRequest) -> SearchPage:
        category = str(request.filters.get("category") or "all")
        raw = self._client.search(
            request.query.strip(), category, request.cursor, request.refresh
        )
        pages = _pages(raw)
        continuation = raw.get("continue")
        offset = continuation.get("gsroffset") if isinstance(continuation, Mapping) else None
        next_cursor = f"s:{offset}" if isinstance(offset, int) else None
        return SearchPage(
            tuple(
                item
                for row in pages
                if (item := normalize_search_item(row)) is not None
            ),
            next_cursor,
        )

    def detail(self, item: AssetItem) -> AssetDetail:
        self._require_item(item)
        title = item.metadata.get("file_title")
        if not isinstance(title, str):
            raise SpiderError("invalid_asset", "Commons 视频缺少文件标题")
        return normalize_detail(item, self._client.detail(title, refresh=False))

    def download(self, item: AssetItem, output_root: Path) -> DownloadResult:
        detail = self.detail(item)
        resource = next(
            (entry for entry in detail.media if entry.role == "download"), None
        )
        if resource is None:
            raise SpiderError("video_unavailable", "当前视频没有可下载文件", status=404)
        return self._downloader.download(resource, item.id, output_root)

    @staticmethod
    def _require_item(item: AssetItem) -> None:
        if item.provider != "commons-video" or not item.id.isdigit() or item.id == "0":
            raise SpiderError("invalid_asset", "Commons 视频素材数据无效")


def _pages(raw: Mapping[str, object]) -> tuple[Mapping[str, object], ...]:
    query = raw.get("query")
    pages = query.get("pages") if isinstance(query, Mapping) else None
    if not isinstance(pages, list):
        return ()
    return tuple(page for page in pages if isinstance(page, Mapping))
