"""Are.na 公开频道策略，只取图片块，不使用已受限的全站图片搜索。"""

from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit

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
    SpiderError,
)
from .curated_download import CuratedDownloader
from .museum_assets import (
    category,
    image_url,
    integer,
    object_data,
    page_number,
    plain_text,
    require_item,
)
from .public_json_client import PublicJsonClient


_CHANNELS = {
    "graphic": ("平面设计", "graphic-design-rvbh_juj1ds"),
    "photography": ("当代摄影", "photography-cxe5v9c6loo"),
    "typography": ("字体与排版", "typography-y174z5sgeya"),
}


from .download_policy import HostDownloadPolicy

IMAGE_POLICY = HostDownloadPolicy(
    "arena", lambda host: host in {"images.are.na", "d2w9rnfcy7mm78.cloudfront.net"}
)


class ArenaProvider:
    id = "arena"
    image_policy = IMAGE_POLICY

    def __init__(
        self, client: PublicJsonClient, downloader: CuratedDownloader | None = None
    ) -> None:
        self._client = client
        self._downloader = downloader or CuratedDownloader(self.image_policy)

    def descriptor(self) -> ProviderDescriptor:
        return ProviderDescriptor(
            self.id,
            "Are.na",
            "设计师公开收藏频道",
            presentation=ProviderPresentation(
                "editorial",
                "摄影与设计",
                "ARE.NA",
                "ARE.NA",
                20,
                60,
                "按当前搜索条件新增最多100张素材，已有缓存将跳过",
                True,
            ),
            filters=(
                FilterField(
                    "category",
                    "精选频道",
                    "select",
                    "graphic",
                    tuple(FilterOption(key, row[0]) for key, row in _CHANNELS.items()),
                ),
            ),
            capabilities=ProviderCapabilities(
                cache=True, bulk_download=True, pagination="page"
            ),
            search_placeholder="留空浏览精选；或粘贴公开 Are.na 频道链接（非关键词搜索）",
        )

    def status(self) -> ProviderStatus:
        return ProviderStatus(True, message="公开灵感频道 · 支持频道链接")

    def search(self, request: SearchRequest) -> SearchPage:
        page = page_number(request)
        selected = category(request, _CHANNELS, "graphic")
        slug = _CHANNELS[selected][1]
        if request.query.strip():
            slug = _channel_slug(request.query.strip())
        result = self._client.get(
            f"channels/{slug}",
            {"per": 24, "page": page, "direction": "desc"},
            refresh=request.refresh,
        )
        data = object_data(result.data)
        if data.get("status") == "private":
            raise SpiderError("private_channel", "仅支持公开 Are.na 频道")
        rows = data.get("contents")
        if not isinstance(rows, list):
            raise SpiderError(
                "source_invalid_response", "Are.na 频道数据无效", status=502
            )
        items = tuple(
            item
            for row in rows
            if isinstance(row, Mapping)
            if (item := _item(row)) is not None
        )
        total = integer(data.get("length"))
        return SearchPage(
            items, str(page + 1) if page * 24 < total and page < 10000 else None
        )

    def detail(self, item: AssetItem) -> AssetDetail:
        require_item(item, self.image_policy)
        original = image_url(item.metadata.get("original_url"), self.image_policy)
        if not original:
            raise SpiderError("invalid_asset", "Are.na 图片地址无效")
        return AssetDetail(
            replace(item, preview_url=original),
            (original,),
            content=plain_text(item.metadata.get("description")),
        )

    def download(self, item: AssetItem, output_root: Path) -> DownloadResult:
        return self._downloader.download(
            self.detail(item).images[0], item.id, output_root
        )


def _channel_slug(query: str) -> str:
    try:
        parsed = urlsplit(query)
        port = parsed.port
    except ValueError as exc:
        raise SpiderError("invalid_channel", "Are.na 频道链接格式无效") from exc
    parts = parsed.path.strip("/").split("/")
    if (
        parsed.scheme != "https"
        or parsed.hostname not in {"are.na", "www.are.na"}
        or parsed.username
        or parsed.password
        or port not in {None, 443}
        or len(parts) != 2
        or parts[0] in {"block", "blocks", "search"}
        or not all(re.fullmatch(r"[A-Za-z0-9_-]+", part) for part in parts)
    ):
        raise SpiderError(
            "invalid_channel", "请粘贴公开 Are.na 频道链接，或清空输入后选择精选频道"
        )
    return parts[1]


def _item(row: Mapping[str, Any]) -> AssetItem | None:
    if row.get("class") != "Image" or row.get("visibility", "public") != "public":
        return None
    item_id = integer(row.get("id"))
    images = object_data(row.get("image"))
    original = image_url(object_data(images.get("original")).get("url"), IMAGE_POLICY)
    preview = (
        image_url(object_data(images.get("thumb")).get("url"), IMAGE_POLICY) or original
    )
    if not item_id or not original:
        return None
    author = plain_text(object_data(row.get("user")).get("full_name"))
    return AssetItem(
        "arena",
        str(item_id),
        kind="editorial",
        title=plain_text(row.get("title")) or f"灵感图片 {item_id}",
        author="收藏：" + author if author else "公开频道",
        preview_url=preview,
        source_url=f"https://www.are.na/block/{item_id}",
        created_at=plain_text(row.get("created_at")),
        metadata={
            "original_url": original,
            "description": plain_text(row.get("description") or row.get("content")),
        },
    )
