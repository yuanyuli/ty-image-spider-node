"""V&A 馆藏：真实分类词表、作品摘要和 IIIF 图片。"""

from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping

from ..models import (
    AssetDetail,
    AssetItem,
    DownloadResult,
    ProviderCapabilities,
    ProviderDescriptor,
    ProviderPresentation,
    ProviderStatus,
    SearchPage,
    SearchRequest,
    SpiderError,
)
from .curated_download import CuratedDownloader
from .museum_client import MuseumClient
from .museum_assets import (
    category,
    category_field,
    collection_detail,
    integer,
    object_data,
    page_number,
    plain_text,
    records,
    require_item,
)


_CATEGORIES = {
    "all": ("全部有图馆藏", ""),
    "photography": ("摄影", "THES48910"),
    "fashion": ("时装", "THES48957"),
    "posters": ("海报", "THES252963"),
    "design": ("设计", "THES48968"),
    "textile": ("纺织与纹样", "THES48885"),
    "architecture": ("建筑", "THES48993"),
    "ceramics": ("陶瓷", "THES48982"),
}


class VamProvider:
    id = "vam"

    def __init__(
        self, client: MuseumClient, downloader: CuratedDownloader | None = None
    ) -> None:
        self._client = client
        self._downloader = downloader or CuratedDownloader()

    def descriptor(self) -> ProviderDescriptor:
        return ProviderDescriptor(
            self.id,
            "V&A",
            "V&A 博物馆 · 摄影、时装与设计",
            presentation=ProviderPresentation(
                "collections",
                "艺术馆藏",
                "V&A",
                "V&A MUSEUM",
                30,
                30,
                "按当前搜索条件新增最多100张素材，已有缓存将跳过",
                True,
            ),
            filters=(category_field(_CATEGORIES, "photography"),),
            capabilities=ProviderCapabilities(
                bulk_download=True, pagination="page", cache=True
            ),
            search_placeholder="可留空浏览分类；作品名或作者建议用英文",
        )

    def status(self) -> ProviderStatus:
        return ProviderStatus(True, message="公开馆藏 · 摄影 / 时装 / 设计")

    def search(self, request: SearchRequest) -> SearchPage:
        page = page_number(request)
        selected = category(request, _CATEGORIES, "photography")
        params: dict[str, object] = {"images_exist": 1, "page_size": 24, "page": page}
        if _CATEGORIES[selected][1]:
            params["id_category"] = _CATEGORIES[selected][1]
        if request.query.strip():
            params["q"] = request.query.strip()
        data = self._client.get("objects/search", params, refresh=request.refresh)
        items = tuple(
            item
            for row in records(data, "records")
            if (item := _artwork(row)) is not None
        )
        last = min(integer(object_data(data.get("info")).get("pages")), 10000)
        return SearchPage(items, str(page + 1) if page < last else None)

    def detail(self, item: AssetItem) -> AssetDetail:
        require_item(item, self.id)
        data = self._client.get(f"museumobject/{item.id}", {})
        record = object_data(data.get("record"))
        if not record or record.get("systemNumber", item.id) != item.id:
            raise SpiderError(
                "vam_invalid_response", "V&A 返回的作品详情无效", status=502
            )
        description = plain_text(
            record.get("summaryDescription")
            or record.get("briefDescription")
            or record.get("physicalDescription")
        )
        materials = record.get("materials")
        medium = (
            " / ".join(
                plain_text(value.get("text"))
                for value in materials
                if isinstance(value, Mapping)
            )
            if isinstance(materials, list)
            else ""
        )
        enriched = replace(
            item,
            metadata={**item.metadata, "description": description, "medium": medium},
        )
        return collection_detail(enriched, self.id)

    def download(self, item: AssetItem, output_root: Path) -> DownloadResult:
        # 搜索结果已含主图地址；下载不依赖作品文字详情接口。
        return self._downloader.download(
            collection_detail(item, self.id).images[0], self.id, item.id, output_root
        )


def _artwork(raw: Mapping[str, Any]) -> AssetItem | None:
    item_id, image_id = raw.get("systemNumber"), raw.get("_primaryImageId")
    if not isinstance(item_id, str) or not re.fullmatch(r"O[0-9]+", item_id):
        return None
    if not isinstance(image_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", image_id):
        return None
    base = f"https://framemark.vam.ac.uk/collections/{image_id}/full/"
    high = object_data(raw.get("_images")).get("imageResolution") == "high"
    return AssetItem(
        "vam",
        item_id,
        kind="collection",
        title=plain_text(raw.get("_primaryTitle"))
        or f"{plain_text(raw.get('objectType')) or '馆藏'} · {item_id}",
        author=plain_text(object_data(raw.get("_primaryMaker")).get("name")),
        created_at=plain_text(raw.get("_primaryDate")),
        preview_url=base + ("!800,800" if high else "full") + "/0/default.jpg",
        source_url=f"https://collections.vam.ac.uk/item/{item_id}/",
        metadata={
            "original_url": base
            + ("!1680,1680" if high else "full")
            + "/0/default.jpg",
            "collection": "Victoria and Albert Museum",
            "category": plain_text(raw.get("objectType")),
            "place": plain_text(raw.get("_primaryPlace")),
            "rights": "V&A 藏品图片；使用条件见来源页面",
            "resolution_note": "来源提供高清图片"
            if high
            else "来源仅提供较低分辨率图片",
        },
    )
