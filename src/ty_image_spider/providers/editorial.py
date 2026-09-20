"""WordPress 公开专题策略：分类、分页与专题图集，网站差异通过配置注入。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit

from ..models import (
    AssetDetail,
    AssetItem,
    DownloadResult,
    FilterField,
    FilterOption,
    JsonValue,
    ProviderCapabilities,
    ProviderDescriptor,
    ProviderStatus,
    SearchPage,
    SearchRequest,
    SpiderError,
)
from .curated_download import CuratedDownloader
from .editorial_images import article_images
from .editorial_sources import EditorialSource
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


class EditorialProvider:
    def __init__(
        self,
        source: EditorialSource,
        client: PublicJsonClient,
        downloader: CuratedDownloader | None = None,
    ) -> None:
        self._source = source
        self.id = source.id
        self._client = client
        self._downloader = downloader or CuratedDownloader()

    def descriptor(self) -> ProviderDescriptor:
        return ProviderDescriptor(
            self.id,
            self._source.label,
            "摄影与设计专题图集",
            presentation=self._source.presentation,
            filters=(
                FilterField(
                    "category",
                    "专题分类",
                    "select",
                    self._source.default,
                    tuple(
                        FilterOption(key, row[0])
                        for key, row in self._source.categories.items()
                    ),
                ),
            ),
            capabilities=ProviderCapabilities(cache=True, pagination="page"),
            search_placeholder="可留空浏览中文分类；关键词建议使用英文",
        )

    def status(self) -> ProviderStatus:
        return ProviderStatus(True, message="公开专题 · 每项含一组图片")

    def search(self, request: SearchRequest) -> SearchPage:
        page = page_number(request)
        choice = category(request, self._source.categories, self._source.default)
        params: dict[str, object] = {
            "per_page": self._source.page_size,
            "page": page,
            "_embed": "1",
        }
        _, taxonomy, value = self._source.categories[choice]
        if taxonomy:
            params[taxonomy] = value
        if request.query.strip():
            params["search"] = request.query.strip()
        response = self._client.get("posts", params, refresh=request.refresh)
        if not isinstance(response.data, list):
            raise SpiderError("source_invalid_response", "专题列表数据无效", status=502)
        items = tuple(
            item
            for row in response.data
            if isinstance(row, Mapping)
            if (item := self._item(row)) is not None
        )
        return SearchPage(
            items, str(page + 1) if page < min(response.total_pages, 10000) else None
        )

    def _item(self, row: Mapping[str, Any]) -> AssetItem | None:
        item_id = integer(row.get("id"))
        markup = object_data(row.get("content")).get("rendered")
        images = article_images(markup if isinstance(markup, str) else "", self.id)
        embedded = object_data(row.get("_embedded"))
        media = embedded.get("wp:featuredmedia")
        cover = object_data(media[0]) if isinstance(media, list) and media else {}
        original = image_url(cover.get("source_url"), self.id)
        if original:
            images = (original,) + tuple(url for url in images if url != original)
        if not item_id or not images:
            return None
        sizes = object_data(object_data(cover.get("media_details")).get("sizes"))
        content_previews = article_images(
            markup if isinstance(markup, str) else "", self.id, max_width=800
        )
        medium_preview = image_url(
            object_data(sizes.get("medium_large")).get("source_url"), self.id
        )
        preferred = original if self._source.prefer_original_preview else medium_preview
        preview = preferred or (content_previews[0] if content_previews else images[0])
        authors = embedded.get("author")
        author = (
            plain_text(object_data(authors[0]).get("name"))
            if isinstance(authors, list) and authors
            else ""
        )
        link = row.get("link")
        source_url = (
            link
            if isinstance(link, str)
            and urlsplit(link).scheme == "https"
            and urlsplit(link).hostname == urlsplit(self._source.api_root).hostname
            else self._source.api_root.split("/wp-json/")[0] + f"/?p={item_id}"
        )
        values: list[JsonValue] = list(images[:60])
        return AssetItem(
            self.id,
            str(item_id),
            kind="editorial",
            title=plain_text(object_data(row.get("title")).get("rendered")),
            author="编辑：" + author if author else self._source.label,
            preview_url=preview,
            source_url=source_url,
            created_at=plain_text(row.get("date")),
            image_count=len(values),
            download_mode="gallery",
            metadata={
                "images": values,
                "description": plain_text(
                    object_data(row.get("excerpt")).get("rendered")
                ),
            },
        )

    def detail(self, item: AssetItem) -> AssetDetail:
        require_item(item, self.id)
        raw = item.metadata.get("images")
        if not isinstance(raw, list) or not 1 <= len(raw) <= 60:
            raise SpiderError("invalid_asset", "专题图集数据无效")
        images = tuple(image_url(value, self.id) for value in raw)
        if not all(images):
            raise SpiderError("invalid_asset", "专题图片地址无效")
        return AssetDetail(
            item, images, content=plain_text(item.metadata.get("description"))
        )

    def download(self, item: AssetItem, output_root: Path) -> DownloadResult:
        images = self.detail(item).images
        files: list[str] = []
        failed = 0
        for index, url in enumerate(images, 1):
            try:
                files.extend(
                    self._downloader.download(
                        url, self.id, f"{item.id}-{index}", output_root
                    ).files
                )
            except SpiderError:
                failed += 1
        if not files:
            raise SpiderError("download_failed", "图集下载失败，请稍后重试", status=502)
        return DownloadResult(
            tuple(files),
            f"图集已下载 {len(files)} 张"
            + (f"，失败 {failed} 张，可重试" if failed else ""),
        )
