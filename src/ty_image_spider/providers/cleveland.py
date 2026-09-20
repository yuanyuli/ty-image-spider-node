"""克利夫兰艺术博物馆：分类检索和偏移分页，选择高清 JPG 而非巨型 TIFF。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping
from urllib.parse import quote

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
    image_url,
    integer,
    object_data,
    page_number,
    plain_text,
    records,
)


_CATEGORIES = {
    "all": ("全部有图馆藏", ""),
    "photography": ("摄影", "Photograph"),
    "painting": ("绘画", "Painting"),
    "sculpture": ("雕塑", "Sculpture"),
    "drawing": ("素描", "Drawing"),
    "prints": ("版画", "Print"),
    "textile": ("纺织", "Textile"),
}


class ClevelandProvider:
    id = "cleveland"

    def __init__(
        self, client: MuseumClient, downloader: CuratedDownloader | None = None
    ) -> None:
        self._client = client
        self._downloader = downloader or CuratedDownloader()

    def descriptor(self) -> ProviderDescriptor:
        return ProviderDescriptor(
            self.id,
            "克利夫兰",
            "克利夫兰艺术博物馆 · 经典摄影与艺术",
            filters=(category_field(_CATEGORIES, "photography"),),
            capabilities=ProviderCapabilities(
                bulk_download=True, pagination="page", cache=True
            ),
            search_placeholder="可留空浏览分类；作品名或作者建议用英文",
        )

    def status(self) -> ProviderStatus:
        return ProviderStatus(True, message="公开馆藏 · 高清 JPG")

    def search(self, request: SearchRequest) -> SearchPage:
        page = page_number(request)
        selected = category(request, _CATEGORIES, "photography")
        params: dict[str, object] = {
            "has_image": 1,
            "skip": (page - 1) * 24,
            "limit": 24,
        }
        if _CATEGORIES[selected][1]:
            params["type"] = _CATEGORIES[selected][1]
        if request.query.strip():
            params["q"] = request.query.strip()
        data = self._client.get("artworks/", params, refresh=request.refresh)
        items = tuple(
            item for row in records(data, "data") if (item := _artwork(row)) is not None
        )
        total = integer(object_data(data.get("info")).get("total"))
        return SearchPage(
            items, str(page + 1) if page * 24 < total and page < 10000 else None
        )

    def detail(self, item: AssetItem) -> AssetDetail:
        return collection_detail(item, self.id)

    def download(self, item: AssetItem, output_root: Path) -> DownloadResult:
        return self._downloader.download(
            self.detail(item).images[0], self.id, item.id, output_root
        )


def _artwork(raw: Mapping[str, Any]) -> AssetItem | None:
    item_id = integer(raw.get("id"))
    images = object_data(raw.get("images"))
    preview = image_url(object_data(images.get("web")).get("url"), "cleveland")
    original = (
        image_url(object_data(images.get("print")).get("url"), "cleveland") or preview
    )
    if not item_id or not preview:
        return None
    creators = raw.get("creators")
    author = (
        " / ".join(
            plain_text(entry.get("description"))
            for entry in creators
            if isinstance(entry, Mapping)
        )
        if isinstance(creators, list)
        else ""
    )
    accession = quote(str(raw.get("accession_number") or ""), safe="")
    return AssetItem(
        "cleveland",
        str(item_id),
        kind="collection",
        title=plain_text(raw.get("title")) or f"馆藏 {item_id}",
        author=author,
        created_at=plain_text(raw.get("creation_date")),
        preview_url=preview,
        source_url=f"https://www.clevelandart.org/art/{accession}"
        if accession
        else "https://www.clevelandart.org/art/collection/search",
        metadata={
            "original_url": original,
            "collection": "克利夫兰艺术博物馆",
            "category": plain_text(raw.get("type")),
            "medium": plain_text(raw.get("technique")),
            "dimensions": plain_text(raw.get("measurements")),
            "description": plain_text(raw.get("description")),
            "rights": " · ".join(
                filter(
                    None,
                    [
                        plain_text(raw.get("share_license_status")),
                        plain_text(raw.get("copyright")),
                    ],
                )
            )
            or "使用条件见来源页面",
        },
    )
