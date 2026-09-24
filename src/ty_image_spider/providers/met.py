"""纽约大都会艺术博物馆公共领域馆藏。"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Mapping, Protocol

from ..domain import (
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
from .download_policy import HostDownloadPolicy
from .museum_assets import plain_text
from .public_json_client import PublicJsonClient


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

IMAGE_POLICY = HostDownloadPolicy(
    "met", lambda host: host == "images.metmuseum.org", id_pattern=r"[1-9][0-9]*"
)


class Downloader(Protocol):
    def download(self, url: str, item_id: str, output_root: Path) -> DownloadResult: ...


class MetClient:
    def __init__(self, client: PublicJsonClient) -> None:
        self._client = client

    def search(self, query: str, department_id: int | None) -> list[int]:
        params: dict[str, object] = {
            "hasImages": "true",
            "isPublicDomain": "true",
            "q": query or "*",
        }
        if department_id is not None:
            params["departmentId"] = department_id
        response = self._client.get("search", params)
        data = response.data
        ids = data.get("objectIDs") if isinstance(data, Mapping) else None
        if ids is None:
            return []
        if not isinstance(ids, list):
            raise SpiderError("met_invalid_response", "大都会博物馆搜索结果无效", status=502)
        return [
            value
            for value in ids
            if isinstance(value, int) and not isinstance(value, bool) and value > 0
        ]

    def object(self, object_id: int) -> Mapping[str, Any]:
        if object_id < 1:
            raise SpiderError("invalid_asset", "大都会博物馆素材 ID 无效")
        data = self._client.get(f"objects/{object_id}", {}).data
        if not isinstance(data, Mapping):
            raise SpiderError("met_invalid_response", "大都会博物馆作品详情无效", status=502)
        return data

    def objects(self, object_ids: list[int]) -> list[Mapping[str, Any]]:
        if not object_ids:
            return []

        def fetch(object_id: int) -> Mapping[str, Any] | None:
            try:
                return self.object(object_id)
            except SpiderError:
                return None

        with ThreadPoolExecutor(max_workers=min(6, len(object_ids))) as executor:
            rows = executor.map(fetch, object_ids)
            return [row for row in rows if row is not None]


class MetProvider:
    id = "met"
    image_policy = IMAGE_POLICY

    def __init__(self, client: MetClient, downloader: Downloader) -> None:
        self._client = client
        self._downloader = downloader

    def descriptor(self) -> ProviderDescriptor:
        return ProviderDescriptor(
            presentation=ProviderPresentation(
                "collections", "艺术馆藏", "MET", "THE MET", 30, 70,
                "按当前分类新增最多100件公共领域馆藏，已有缓存将跳过", True,
            ),
            id=self.id,
            label="纽约大都会艺术博物馆",
            description="浏览 The Met 有图片的公共领域馆藏",
            filters=(
                FilterField(
                    "category", "馆藏分类", "select", "all",
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
        query = request.query.strip() or preset
        ids = self._client.search(query, department_id)
        start = (page - 1) * _PAGE_SIZE
        selected = ids[start : start + _PAGE_SIZE]
        items = tuple(
            item
            for row in self._client.objects(selected)
            if (item := _artwork(row)) is not None
        )
        next_cursor = str(page + 1) if start + _PAGE_SIZE < len(ids) else None
        return SearchPage(items, next_cursor)

    def detail(self, item: AssetItem) -> AssetDetail:
        _require_item(item)
        verified = _artwork(self._client.object(int(item.id)))
        if verified is None or verified.id != item.id:
            raise SpiderError(
                "met_invalid_response", "大都会博物馆作品不再提供公共领域图片", status=502
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


def _artwork(raw: Mapping[str, Any]) -> AssetItem | None:
    object_id = raw.get("objectID")
    original = raw.get("primaryImage")
    preview = raw.get("primaryImageSmall") or original
    if (
        not isinstance(object_id, int)
        or object_id < 1
        or raw.get("isPublicDomain") is not True
        or not isinstance(original, str)
        or not isinstance(preview, str)
    ):
        return None
    try:
        IMAGE_POLICY.validate_url(original)
        IMAGE_POLICY.validate_url(preview)
    except SpiderError:
        return None
    tags_value = raw.get("tags")
    tags = tuple(
        text
        for entry in tags_value
        if isinstance(entry, Mapping) and (text := plain_text(entry.get("term")))
    ) if isinstance(tags_value, list) else ()
    object_url = plain_text(raw.get("objectURL"))
    if not object_url.startswith("https://www.metmuseum.org/art/collection/search/"):
        object_url = f"https://www.metmuseum.org/art/collection/search/{object_id}"
    return AssetItem(
        provider="met",
        id=str(object_id),
        kind="collection",
        preview_url=preview,
        source_url=object_url,
        title=plain_text(raw.get("title")) or f"馆藏 {object_id}",
        author=plain_text(raw.get("artistDisplayName")),
        created_at=plain_text(raw.get("objectDate")),
        tags=tags[:12],
        metadata={
            "original_url": original,
            "collection": "The Metropolitan Museum of Art",
            "category": plain_text(raw.get("department")),
            "medium": plain_text(raw.get("medium")),
            "description": plain_text(raw.get("creditLine")),
            "rights": "Public Domain",
        },
    )


def _page_number(cursor: str | None) -> int:
    raw = cursor or "1"
    if not re.fullmatch(r"[1-9][0-9]{0,4}", raw):
        raise SpiderError("invalid_cursor", "大都会博物馆页码无效")
    return int(raw)


def _require_item(item: AssetItem) -> None:
    if item.provider != "met" or not _SAFE_ID.fullmatch(item.id):
        raise SpiderError("invalid_asset", "大都会博物馆素材数据无效")
