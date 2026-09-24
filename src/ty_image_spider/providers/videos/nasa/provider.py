"""NASA 视频 Provider 编排。"""

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
from .client import NasaVideoClient
from .normalizer import SAFE_ID, normalize_detail, normalize_search_item


CATEGORIES = {
    "space": ("太空", "space"),
    "earth": ("地球", "earth from space"),
    "moon": ("月球", "moon"),
    "mars": ("火星", "mars"),
    "apollo": ("阿波罗计划", "apollo"),
    "telescopes": ("太空望远镜", "space telescope"),
    "astronauts": ("宇航员", "astronaut"),
    "all": ("全部视频", ""),
}
IMAGE_POLICY = HostDownloadPolicy(
    "nasa-video",
    lambda host: host == "images-assets.nasa.gov",
    id_pattern=SAFE_ID.pattern,
)


class Downloader(Protocol):
    def download(
        self, resource: MediaResource, item_id: str, output_root: Path
    ) -> DownloadResult: ...


class NasaVideoProvider:
    id = "nasa-video"
    image_policy = IMAGE_POLICY

    def __init__(self, client: NasaVideoClient, downloader: Downloader) -> None:
        self._client = client
        self._downloader = downloader

    def descriptor(self) -> ProviderDescriptor:
        return ProviderDescriptor(
            id=self.id,
            label="NASA 视频",
            presentation=ProviderPresentation(
                "videos",
                "视频素材",
                "NASA",
                "NASA VIDEO LIBRARY",
                60,
                30,
                "按当前条件新增最多100条封面与资料；视频按需播放和下载",
            ),
            description="浏览 NASA 官方太空、地球与航天历史视频",
            filters=(
                FilterField(
                    "category",
                    "视频分类",
                    "select",
                    "space",
                    tuple(
                        FilterOption(key, value[0])
                        for key, value in CATEGORIES.items()
                    ),
                ),
            ),
            capabilities=ProviderCapabilities(
                bulk_download=False, pagination="page", cache=True
            ),
            search_placeholder="可留空浏览分类；任务、天体和人物建议使用英文",
        )

    def status(self) -> ProviderStatus:
        return ProviderStatus(True, message="NASA 官方公开视频库")

    def search(self, request: SearchRequest) -> SearchPage:
        page = _page(request.cursor)
        category = str(request.filters.get("category") or "space")
        if category not in CATEGORIES:
            raise SpiderError("invalid_category", "NASA 视频分类无效")
        query = " ".join(
            part for part in (CATEGORIES[category][1], request.query.strip()) if part
        )
        raw = self._client.search(query, page, request.refresh)
        collection = raw.get("collection")
        values = collection if isinstance(collection, Mapping) else {}
        rows = values.get("items")
        items = tuple(
            item
            for row in rows
            if isinstance(row, Mapping)
            and (item := normalize_search_item(row)) is not None
        ) if isinstance(rows, list) else ()
        metadata = values.get("metadata")
        total = metadata.get("total_hits") if isinstance(metadata, Mapping) else 0
        next_cursor = str(page + 1) if isinstance(total, int) and page * 24 < total else None
        return SearchPage(items, next_cursor)

    def detail(self, item: AssetItem) -> AssetDetail:
        self._require_item(item)
        manifest = item.metadata.get("manifest_url")
        if not isinstance(manifest, str):
            raise SpiderError("invalid_asset", "NASA 视频缺少资源清单")
        return normalize_detail(item, self._client.manifest(manifest, refresh=False))

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
        if item.provider != "nasa-video" or not SAFE_ID.fullmatch(item.id):
            raise SpiderError("invalid_asset", "NASA 视频素材数据无效")


def _page(cursor: str | None) -> int:
    if cursor is None:
        return 1
    if not cursor.isdigit() or not 1 <= int(cursor) <= 10000:
        raise SpiderError("invalid_cursor", "NASA 视频分页游标无效")
    return int(cursor)

