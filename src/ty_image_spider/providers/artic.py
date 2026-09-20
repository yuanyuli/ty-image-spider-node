"""芝加哥艺术博物馆：按真实作品类型检索，通过 IIIF 提供图片。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

from ..models import (
    AssetDetail,
    AssetItem,
    DownloadResult,
    ProviderCapabilities,
    ProviderDescriptor,
    ProviderStatus,
    SearchPage,
    SearchRequest,
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
)


_CATEGORIES = {
    "all": ("全部有图馆藏", None),
    "painting": ("绘画", 1),
    "photography": ("摄影", 2),
    "design": ("设计", 31),
    "graphic": ("平面设计", 32),
    "architecture": ("建筑图纸", 34),
    "sculpture": ("雕塑", 3),
    "textile": ("纺织", 5),
    "fashion": ("服装与配饰", 12),
    "prints": ("版画", 18),
}
_FIELDS = "id,title,image_id,artist_display,date_display,medium_display,dimensions,description,is_public_domain,copyright_notice,artwork_type_title,department_title"


class ArticProvider:
    id = "artic"

    def __init__(
        self, client: MuseumClient, downloader: CuratedDownloader | None = None
    ) -> None:
        self._client = client
        self._downloader = downloader or CuratedDownloader()

    def descriptor(self) -> ProviderDescriptor:
        return ProviderDescriptor(
            self.id,
            "芝加哥艺术",
            "芝加哥艺术博物馆 · 绘画、摄影与设计",
            filters=(category_field(_CATEGORIES, "painting"),),
            capabilities=ProviderCapabilities(
                bulk_download=True, pagination="page", cache=True
            ),
            search_placeholder="可留空浏览分类；作品名或作者建议用英文",
        )

    def status(self) -> ProviderStatus:
        return ProviderStatus(True, message="公开馆藏 · 无需账号")

    def search(self, request: SearchRequest) -> SearchPage:
        page = page_number(request)
        selected = category(request, _CATEGORIES, "painting")
        filters: list[dict[str, Any]] = [{"exists": {"field": "image_id"}}]
        if (type_id := _CATEGORIES[selected][1]) is not None:
            filters.append({"term": {"artwork_type_id": type_id}})
        params: dict[str, Any] = {
            "query": {"bool": {"filter": filters}},
            "fields": _FIELDS.split(","),
            "page": page,
            "limit": 24,
        }
        if request.query.strip():
            params["q"] = request.query.strip()
        else:
            params["sort"] = [{"id": "desc"}]
        data = self._client.get(
            "artworks/search",
            {"params": json.dumps(params, separators=(",", ":"))},
            refresh=request.refresh,
        )
        items = tuple(
            item for row in records(data, "data") if (item := _artwork(row)) is not None
        )
        total_pages = min(
            integer(object_data(data.get("pagination")).get("total_pages")), 416
        )
        return SearchPage(items, str(page + 1) if page < total_pages else None)

    def detail(self, item: AssetItem) -> AssetDetail:
        return collection_detail(item, self.id)

    def download(self, item: AssetItem, output_root: Path) -> DownloadResult:
        return self._downloader.download(
            self.detail(item).images[0], self.id, item.id, output_root
        )


def _artwork(raw: Mapping[str, Any]) -> AssetItem | None:
    item_id, image_id = integer(raw.get("id")), raw.get("image_id")
    if (
        not item_id
        or not isinstance(image_id, str)
        or not re.fullmatch(r"[a-zA-Z0-9-]+", image_id)
    ):
        return None
    base = f"https://www.artic.edu/iiif/2/{image_id}/full/"
    public = raw.get("is_public_domain") is True
    return AssetItem(
        "artic",
        str(item_id),
        kind="collection",
        title=plain_text(raw.get("title")) or f"馆藏 {item_id}",
        author=plain_text(raw.get("artist_display")),
        created_at=plain_text(raw.get("date_display")),
        preview_url=base + "843,/0/default.jpg",
        source_url=f"https://www.artic.edu/artworks/{item_id}",
        metadata={
            "original_url": base + ("1686" if public else "843") + ",/0/default.jpg",
            "collection": "芝加哥艺术博物馆",
            "category": plain_text(raw.get("artwork_type_title")),
            "medium": plain_text(raw.get("medium_display")),
            "dimensions": plain_text(raw.get("dimensions")),
            "description": plain_text(raw.get("description")),
            "rights": "CC0 / 公共领域"
            if public
            else plain_text(raw.get("copyright_notice"))
            or "非公共领域；使用条件见来源页面",
        },
    )
