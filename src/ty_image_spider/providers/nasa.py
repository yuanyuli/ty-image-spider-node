"""NASA 图片与视频资料库 Provider。"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import quote, urlsplit

from ..models import (
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
)
from .curated_download import CuratedDownloader
from .museum_assets import (
    category,
    collection_detail,
    image_url,
    integer,
    object_data,
    page_number,
    plain_text,
)
from .public_json_client import PublicJsonClient


_CATEGORIES = {
    "space": ("太空影像", "space"),
    "earth": ("地球观测", "earth from space"),
    "moon": ("月球", "moon"),
    "mars": ("火星", "mars"),
    "apollo": ("阿波罗计划", "apollo"),
    "telescopes": ("太空望远镜", "space telescope"),
    "astronauts": ("宇航员", "astronaut"),
    "posters": ("NASA 海报", "NASA poster"),
    "all": ("全部图片", ""),
}
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp")


class NasaProvider:
    id = "nasa"

    def __init__(
        self, client: PublicJsonClient, downloader: CuratedDownloader | None = None
    ) -> None:
        self._client = client
        self._downloader = downloader or CuratedDownloader()

    def descriptor(self) -> ProviderDescriptor:
        return ProviderDescriptor(
            self.id,
            "NASA",
            "太空、地球与航天历史影像",
            presentation=ProviderPresentation(
                "collections",
                "艺术馆藏",
                "NASA",
                "NASA IMAGE LIBRARY",
                30,
                20,
                "按当前搜索条件新增最多100张素材，已有缓存将跳过",
                True,
            ),
            filters=(
                FilterField(
                    "category",
                    "影像分类",
                    "select",
                    "space",
                    tuple(
                        FilterOption(key, entry[0])
                        for key, entry in _CATEGORIES.items()
                    ),
                ),
            ),
            capabilities=ProviderCapabilities(
                bulk_download=True, pagination="page", cache=True
            ),
            search_placeholder="可留空浏览分类；任务、天体和人物建议使用英文",
        )

    def status(self) -> ProviderStatus:
        return ProviderStatus(True, message="NASA 官方公开图片库")

    def search(self, request: SearchRequest) -> SearchPage:
        page = page_number(request)
        selected = category(request, _CATEGORIES, "space")
        _, preset = _CATEGORIES[selected]
        query = " ".join(filter(None, (preset, request.query.strip())))
        params: dict[str, object] = {
            "media_type": "image",
            "page": page,
            "page_size": 24,
        }
        if query:
            params["q"] = query
        response = self._client.get("search", params, refresh=request.refresh)
        collection = object_data(object_data(response.data).get("collection"))
        items = tuple(
            item for row in _rows(collection.get("items")) if (item := self._item(row))
        )
        total = integer(object_data(collection.get("metadata")).get("total_hits"))
        return SearchPage(
            items, str(page + 1) if page < 10000 and page * 24 < total else None
        )

    def _item(self, raw: Mapping[str, Any]) -> AssetItem | None:
        data_rows = _rows(raw.get("data"))
        data = data_rows[0] if data_rows else {}
        nasa_id = plain_text(data.get("nasa_id"))
        item_id = _asset_id(nasa_id)
        variants = _image_variants(raw.get("links"))
        if not item_id or not variants:
            return None
        canonical = [entry for entry in variants if entry[4] == "canonical"]
        original = max(canonical or variants, key=lambda entry: entry[0])
        bounded = [entry for entry in variants if 0 < entry[1] <= 800]
        preview = max(bounded or variants, key=lambda entry: entry[0])
        album = _strings(data.get("album"))
        center = plain_text(data.get("center"))
        author = (
            _first_text(data.get("photographer"))
            or _first_text(data.get("secondary_creator"))
            or center
        )
        description = plain_text(data.get("description") or data.get("description_508"))
        return AssetItem(
            self.id,
            item_id,
            kind="collection",
            title=plain_text(data.get("title")) or nasa_id,
            author=author,
            created_at=plain_text(data.get("date_created")),
            width=original[1],
            height=original[2],
            preview_url=preview[3],
            source_url="https://images.nasa.gov/details/" + quote(nasa_id, safe=""),
            tags=tuple(_strings(data.get("keywords"))[:12]),
            metadata={
                "original_url": original[3],
                "collection": "NASA Image and Video Library",
                "category": " / ".join(album) or center,
                "medium": f"NASA Image ID: {nasa_id}",
                "description": description,
                "rights": "使用条件见 NASA 来源页面",
            },
        )

    def detail(self, item: AssetItem) -> AssetDetail:
        return collection_detail(item, self.id)

    def download(self, item: AssetItem, output_root: Path) -> DownloadResult:
        return self._downloader.download(
            self.detail(item).images[0], self.id, item.id, output_root
        )


def _rows(value: object) -> list[Mapping[str, Any]]:
    return (
        [entry for entry in value if isinstance(entry, Mapping)]
        if isinstance(value, list)
        else []
    )


def _strings(value: object) -> list[str]:
    if isinstance(value, list):
        return [text for entry in value if (text := plain_text(entry))]
    text = plain_text(value)
    return [text] if text else []


def _first_text(value: object) -> str:
    values = _strings(value)
    return values[0] if values else ""


def _asset_id(nasa_id: str) -> str:
    if _SAFE_ID.fullmatch(nasa_id):
        return nasa_id
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", nasa_id).strip("-._")[:96]
    if not slug:
        return ""
    digest = hashlib.sha256(nasa_id.encode("utf-8")).hexdigest()[:12]
    return f"{slug}-{digest}"


def _image_variants(value: object) -> list[tuple[int, int, int, str, str]]:
    found: list[tuple[int, int, int, str, str]] = []
    for link in _rows(value):
        if plain_text(link.get("render")) != "image":
            continue
        url = image_url(link.get("href"), "nasa")
        if not url or not urlsplit(url).path.lower().endswith(_IMAGE_SUFFIXES):
            continue
        width = integer(link.get("width"))
        height = integer(link.get("height"))
        found.append((width * height, width, height, url, plain_text(link.get("rel"))))
    return found
