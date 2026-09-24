"""纽约大都会艺术博物馆公共领域馆藏。"""

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
from .client import MetClient
from .normalizer import IMAGE_POLICY, normalize_artwork


_SAFE_ID = re.compile(r"^[1-9][0-9]*$")
_PAGE_SIZE = 24
_CATEGORIES: dict[str, tuple[str, int | None, str]] = {
    "all": ("精选公共领域馆藏", None, "masterpiece"),
    "paintings": ("欧洲绘画", 11, "painting"),
    "photography": ("摄影", 19, "photography"),
    "modern": ("现代艺术", 21, "modern art"),
    "asian": ("亚洲艺术", 6, "art"),
    "egyptian": ("埃及艺术", 10, "art"),
    "islamic": ("伊斯兰艺术", 14, "art"),
}


class Downloader(Protocol):
    def download(self, url: str, item_id: str, output_root: Path) -> DownloadResult: ...


class MetProvider:
    id = "met"
    image_policy = IMAGE_POLICY

    def __init__(self, client: MetClient, downloader: Downloader) -> None:
        self._client = client
        self._downloader = downloader

    def descriptor(self) -> ProviderDescriptor:
        return ProviderDescriptor(
            presentation=ProviderPresentation(
                "collections",
                "艺术馆藏",
                "MET",
                "THE MET",
                30,
                70,
                "按当前分类新增最多100件公共领域馆藏，已有缓存将跳过",
                True,
            ),
            id=self.id,
            label="纽约大都会艺术博物馆",
            description="浏览 The Met 有图片的公共领域馆藏",
            filters=(
                FilterField(
                    "category",
                    "馆藏分类",
                    "select",
                    "all",
                    tuple(
                        FilterOption(key, value[0])
                        for key, value in _CATEGORIES.items()
                    ),
                ),
            ),
            capabilities=ProviderCapabilities(
                bulk_download=True, pagination="page", cache=True
            ),
            search_placeholder="可留空浏览；作品名或作者建议使用英文",
        )

    def status(self) -> ProviderStatus:
        return ProviderStatus(True, message="官方公共领域馆藏")

    def search(self, request: SearchRequest) -> SearchPage:
        category = str(request.filters.get("category") or "all")
        if category not in _CATEGORIES:
            raise SpiderError("invalid_category", "大都会博物馆分类无效")
        page = _page_number(request.cursor)
        _, department_id, preset = _CATEGORIES[category]
        ids = self._client.search(request.query.strip() or preset, department_id)
        start = (page - 1) * _PAGE_SIZE
        selected = ids[start : start + _PAGE_SIZE]
        items = tuple(
            item
            for row in self._client.objects(selected)
            if (item := normalize_artwork(row)) is not None
        )
        next_cursor = str(page + 1) if start + _PAGE_SIZE < len(ids) else None
        return SearchPage(items, next_cursor)

    def detail(self, item: AssetItem) -> AssetDetail:
        _require_item(item)
        verified = normalize_artwork(self._client.object(int(item.id)))
        if verified is None or verified.id != item.id:
            raise SpiderError(
                "met_invalid_response",
                "大都会博物馆作品不再提供公共领域图片",
                status=502,
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


def _page_number(cursor: str | None) -> int:
    raw = cursor or "1"
    if not re.fullmatch(r"[1-9][0-9]{0,4}", raw):
        raise SpiderError("invalid_cursor", "大都会博物馆页码无效")
    return int(raw)


def _require_item(item: AssetItem) -> None:
    if item.provider != "met" or not _SAFE_ID.fullmatch(item.id):
        raise SpiderError("invalid_asset", "大都会博物馆素材数据无效")
