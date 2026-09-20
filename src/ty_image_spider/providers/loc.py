"""美国国会图书馆图片档案：官方分类、分页与多规格图片。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qs, urlsplit

from ..models import (
    AssetDetail,
    AssetItem,
    DownloadResult,
    FilterField,
    FilterOption,
    ProviderCapabilities,
    ProviderDescriptor,
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
    records,
)
from .public_json_client import PublicJsonClient


_CATEGORIES = {
    "documentary": (
        "纪实摄影",
        "partof:farm security administration/office of war information black-and-white negatives|online-format:image",
        "",
    ),
    "posters": ("经典海报", "subject:posters|online-format:image", ""),
    "portraits": ("历史人像", "subject:portrait photographs|online-format:image", ""),
    "architecture": ("建筑档案", "subject:architecture|online-format:image", ""),
    "travel": ("旅行海报", "online-format:image", "travel posters"),
    "fashion": ("时尚摄影", "online-format:image", "fashion photography"),
    "japanese": ("日本版画", "online-format:image", "Japanese woodblock prints"),
    "all": ("全部图片", "online-format:image", ""),
}
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class LocProvider:
    id = "loc"

    def __init__(
        self, client: PublicJsonClient, downloader: CuratedDownloader | None = None
    ) -> None:
        self._client = client
        self._downloader = downloader or CuratedDownloader()

    def descriptor(self) -> ProviderDescriptor:
        return ProviderDescriptor(
            self.id,
            "美国国会图书馆",
            "历史摄影、海报与视觉档案",
            filters=(
                FilterField(
                    "category",
                    "馆藏分类",
                    "select",
                    "documentary",
                    tuple(
                        FilterOption(key, entry[0])
                        for key, entry in _CATEGORIES.items()
                    ),
                ),
            ),
            capabilities=ProviderCapabilities(
                bulk_download=True, pagination="page", cache=True
            ),
            search_placeholder="可留空浏览中文分类；人名和主题建议用英文",
        )

    def status(self) -> ProviderStatus:
        return ProviderStatus(True, message="官方公开档案 · 摄影 / 海报 / 版画")

    def search(self, request: SearchRequest) -> SearchPage:
        page = page_number(request)
        selected = category(request, _CATEGORIES, "documentary")
        _, facet, preset = _CATEGORIES[selected]
        query = " ".join(filter(None, (preset, request.query.strip())))
        params: dict[str, object] = {
            "fo": "json",
            "c": 24,
            "sp": page,
            "at": "results,pagination",
            "fa": facet,
        }
        if query:
            params["q"] = query
        response = self._client.get("photos", params, refresh=request.refresh)
        data = object_data(response.data)
        items = tuple(
            item for row in records(data, "results") if (item := self._item(row))
        )
        pagination = object_data(data.get("pagination"))
        total = integer(pagination.get("of"))
        has_next = bool(pagination.get("next")) or page * 24 < total
        return SearchPage(items, str(page + 1) if has_next and page < 10000 else None)

    def _item(self, raw: Mapping[str, Any]) -> AssetItem | None:
        item_data = object_data(raw.get("item"))
        item_id = plain_text(item_data.get("id"))
        if not _SAFE_ID.fullmatch(item_id):
            match = re.search(r"/item/([A-Za-z0-9._-]+)/?", plain_text(raw.get("id")))
            item_id = match.group(1) if match else ""
        urls = _image_urls(raw.get("image_url"))
        if not item_id or not _SAFE_ID.fullmatch(item_id) or not urls:
            return None
        original = urls[-1][1]
        previews = [entry for entry in urls if max(entry[0]) <= 800]
        preview = (previews[-1] if previews else urls[0])[1]
        contributors = _strings(item_data.get("contributors")) or _strings(
            raw.get("contributor")
        )
        descriptions = _strings(raw.get("description"))
        source_url = plain_text(raw.get("url"))
        if not _loc_page(source_url):
            source_url = f"https://www.loc.gov/item/{item_id}/"
        rights = plain_text(
            item_data.get("rights_information")
            or item_data.get("rights_advisory")
            or raw.get("rights")
        )
        return AssetItem(
            self.id,
            item_id,
            kind="collection",
            title=plain_text(raw.get("title")) or f"档案 {item_id}",
            author=" / ".join(contributors),
            created_at=plain_text(raw.get("date")),
            preview_url=preview,
            source_url=source_url,
            tags=tuple(_strings(raw.get("subject"))[:12]),
            metadata={
                "original_url": original,
                "collection": "Library of Congress",
                "category": " / ".join(_strings(raw.get("original_format"))),
                "medium": plain_text(item_data.get("medium_brief")),
                "description": " ".join(descriptions),
                "rights": rights or "使用条件见来源页面",
            },
        )

    def detail(self, item: AssetItem) -> AssetDetail:
        return collection_detail(item, self.id)

    def download(self, item: AssetItem, output_root: Path) -> DownloadResult:
        return self._downloader.download(
            self.detail(item).images[0], self.id, item.id, output_root
        )


def _strings(value: object) -> list[str]:
    if isinstance(value, list):
        return [text for entry in value if (text := plain_text(entry))]
    text = plain_text(value)
    return [text] if text else []


def _image_urls(value: object) -> list[tuple[tuple[int, int], str]]:
    if not isinstance(value, list):
        return []
    found: list[tuple[tuple[int, int], str]] = []
    for entry in value:
        url = image_url(entry, "loc")
        if not url or not urlsplit(url).path.lower().endswith(
            (".jpg", ".jpeg", ".png", ".webp")
        ):
            continue
        fragment = parse_qs(urlsplit(url).fragment)
        width = integer((fragment.get("w") or ["0"])[0])
        height = integer((fragment.get("h") or ["0"])[0])
        found.append(((width, height), url))
    return sorted(found, key=lambda entry: entry[0][0] * entry[0][1])


def _loc_page(value: str) -> bool:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False
    return parsed.scheme == "https" and parsed.hostname in {"loc.gov", "www.loc.gov"}
