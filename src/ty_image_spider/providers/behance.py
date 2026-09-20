"""Behance 公开设计与摄影项目。"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping

from ..models import (
    AssetDetail,
    AssetItem,
    DownloadResult,
    FilterField,
    FilterOption,
    ProviderDescriptor,
    ProviderPresentation,
    ProviderCapabilities,
    ProviderStatus,
    SearchPage,
    SearchRequest,
    SpiderError,
)
from .curated_client import BehanceClient
from .curated_download import CuratedDownloader


from .download_policy import HostDownloadPolicy

IMAGE_POLICY = HostDownloadPolicy(
    "behance", lambda host: host.startswith("mir-") and host.endswith(".behance.net")
)


class BehanceProvider:
    id = "behance"
    image_policy = IMAGE_POLICY

    def __init__(
        self, client: BehanceClient, downloader: CuratedDownloader | None = None
    ) -> None:
        self._client = client
        self._downloader = downloader or CuratedDownloader(self.image_policy)

    def descriptor(self) -> ProviderDescriptor:
        return ProviderDescriptor(
            self.id,
            "Behance",
            "设计与摄影项目画廊",
            (
                FilterField(
                    "category",
                    "精选画廊（留空关键词时）",
                    "select",
                    "graphic-design",
                    (
                        FilterOption("graphic-design", "平面设计"),
                        FilterOption("photography", "摄影"),
                    ),
                ),
            ),
            presentation=ProviderPresentation(
                "editorial",
                "摄影与设计",
                "B",
                "BEHANCE",
                20,
                10,
                "按当前搜索条件新增最多100张素材，已有缓存将跳过",
                True,
            ),
            capabilities=ProviderCapabilities(cache=True),
        )

    def status(self) -> ProviderStatus:
        return ProviderStatus(True, message="公开项目画廊")

    def search(self, request: SearchRequest) -> SearchPage:
        category = str(request.filters.get("category") or "graphic-design")
        if category not in {"graphic-design", "photography"}:
            category = "graphic-design"
        projects, next_cursor = self._client.projects(
            category, request.query.strip(), request.cursor
        )
        return SearchPage(
            tuple(item for raw in projects if (item := _project(raw)) is not None),
            next_cursor,
        )

    def detail(self, item: AssetItem) -> AssetDetail:
        _require(item)
        images = self._client.images(item.id)
        if images:
            return AssetDetail(replace(item, image_count=len(images)), images)
        original = item.metadata.get("original_url")
        image = original if isinstance(original, str) and original else item.preview_url
        return AssetDetail(item, (image,) if image else ())

    def download(self, item: AssetItem, output_root: Path) -> DownloadResult:
        _require(item)
        image = self.detail(item).images[0]
        return self._downloader.download(image, item.id, output_root)


def _project(raw: Mapping[str, Any]) -> AssetItem | None:
    item_id = raw.get("id")
    if not isinstance(item_id, int) or item_id < 1:
        return None
    covers = raw.get("covers")
    available = covers.get("allAvailable", []) if isinstance(covers, Mapping) else []
    images = [
        value
        for value in available
        if isinstance(value, Mapping) and isinstance(value.get("url"), str)
    ]
    if not images:
        return None
    preview = next(
        (value["url"] for value in images if value.get("width") == 404),
        images[0]["url"],
    )
    original = next(
        (value["url"] for value in images if "/original" in value["url"]),
        images[0]["url"],
    )
    owners = raw.get("owners")
    author = (
        owners[0].get("displayName")
        if isinstance(owners, list) and owners and isinstance(owners[0], Mapping)
        else None
    )
    return AssetItem(
        "behance",
        str(item_id),
        preview_url=preview,
        source_url=str(raw.get("url") or ""),
        title=str(raw.get("name") or ""),
        author=author if isinstance(author, str) else None,
        metadata={"original_url": original},
    )


def _require(item: AssetItem) -> None:
    if item.provider != "behance" or not item.id.isdigit():
        raise SpiderError("invalid_asset", "Behance 素材 ID 无效")
