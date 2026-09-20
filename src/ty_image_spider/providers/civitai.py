"""Civitai 素材来源策略。"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable, Mapping

from ..cache import JsonCache
from ..downloads import ImageDownloader
from ..metadata import extract_prompts
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
    SpiderError,
)
from .civitai_client import CivitaiClient


_TAGS = {"Portrait": 1441}
_MAX_PROMPT_SCAN_PAGES = 5
_MAX_PROMPT_ENRICH_ITEMS = 24


class CivitaiProvider:
    id = "civitai"

    def __init__(
        self,
        client: CivitaiClient,
        cache: JsonCache,
        downloader: ImageDownloader,
        *,
        cached_asset: Callable[[AssetItem], AssetItem | None] | None = None,
    ) -> None:
        self._client = client
        self._cache = cache
        self._downloader = downloader
        self._cached_asset = cached_asset

    def descriptor(self) -> ProviderDescriptor:
        return ProviderDescriptor(
            id=self.id,
            label="Civitai",
            description="浏览 civitai.com 与 civitai.red 的公开图片",
            filters=(
                FilterField(
                    "site",
                    "站点",
                    "select",
                    "civitai.com",
                    (
                        FilterOption("civitai.com", "civitai.com"),
                        FilterOption("civitai.red", "civitai.red"),
                    ),
                ),
                FilterField(
                    "period",
                    "时间范围",
                    "select",
                    "AllTime",
                    tuple(
                        FilterOption(value, value)
                        for value in ("AllTime", "Year", "Month", "Week", "Day")
                    ),
                ),
                FilterField(
                    "sort",
                    "排序",
                    "select",
                    "Most Reactions",
                    tuple(
                        FilterOption(value, value)
                        for value in (
                            "Most Reactions",
                            "Most Comments",
                            "Most Collected",
                            "Newest",
                            "Oldest",
                        )
                    ),
                ),
                FilterField("sfw", "仅 SFW", "toggle", True),
                FilterField(
                    "tag",
                    "标签",
                    "select",
                    "",
                    (FilterOption("", "全部"), FilterOption("Portrait", "Portrait")),
                ),
                FilterField("only_with_prompt", "仅含提示词", "toggle", False),
                FilterField("count", "数量", "number", 12, minimum=1, maximum=100),
            ),
            capabilities=ProviderCapabilities(bulk_download=True, cache=True),
        )

    def status(self) -> ProviderStatus:
        return ProviderStatus(True)

    def search(self, request: SearchRequest) -> SearchPage:
        site, params, only_with_prompt = self._search_parameters(request)
        cache_key = self._cache_key(site, params, only_with_prompt)
        raw_limit = params.get("limit")
        target_count = raw_limit if isinstance(raw_limit, int) else 12
        try:
            raw_page = self._client.search(site, params)
            items: list[AssetItem] = []
            item_ids: set[str] = set()
            seen_cursors: set[str] = set()
            enriched_count = 0
            pages_scanned = 0
            while True:
                pages_scanned += 1
                for raw in raw_page.items:
                    item = self._normalize(raw, site)
                    cached = (
                        self._cached_asset(item)
                        if self._cached_asset and not request.refresh
                        else None
                    )
                    if cached is not None:
                        item = replace(
                            cached,
                            preview_url=item.preview_url,
                            source_url=item.source_url,
                        )
                    if (
                        cached is None
                        and not item.has_prompt
                        and enriched_count < _MAX_PROMPT_ENRICH_ITEMS
                    ):
                        item = self._with_page_metadata_safe(item, site)
                        enriched_count += 1
                    if (
                        not only_with_prompt or item.has_prompt
                    ) and item.id not in item_ids:
                        items.append(item)
                        item_ids.add(item.id)
                    if len(items) >= target_count:
                        break
                if (
                    len(items) >= target_count
                    or not only_with_prompt
                    or not raw_page.next_cursor
                    or raw_page.next_cursor in seen_cursors
                    or pages_scanned >= _MAX_PROMPT_SCAN_PAGES
                ):
                    break
                seen_cursors.add(raw_page.next_cursor)
                params = {**params, "cursor": raw_page.next_cursor}
                raw_page = self._client.search(site, params)
            page = SearchPage(tuple(items), raw_page.next_cursor)
            self._cache.put(cache_key, page.to_dict())
            return page
        except SpiderError:
            cached = self._cache.get(cache_key, max_age_seconds=None)
            if cached is None:
                raise
            return self._page_from_cache(cached)

    def detail(self, item: AssetItem) -> AssetDetail:
        self._require_item(item)
        site = str(item.metadata.get("site") or "civitai.com")
        page_metadata = self._client.page_metadata(site, item.id)
        merged = dict(item.metadata)
        merged.update(page_metadata)
        prompt, negative = extract_prompts(merged)
        updated = replace(
            item,
            prompt=prompt or item.prompt,
            negative_prompt=negative or item.negative_prompt,
            has_prompt=bool(prompt or item.prompt),
            metadata=merged,
        )
        workflow = merged.get("workflow")
        return AssetDetail(
            updated,
            (item.preview_url,) if item.preview_url else (),
            workflow=workflow,
            metadata=merged,
        )

    def _with_page_metadata(self, item: AssetItem, site: str) -> AssetItem:
        metadata = dict(item.metadata)
        metadata.update(self._client.page_metadata(site, item.id))
        prompt, negative = extract_prompts(metadata)
        if metadata.get("hasPositivePrompt") is False:
            prompt, negative = "", ""
            metadata.pop("prompt", None)
            metadata.pop("negativePrompt", None)
            metadata.pop("negative_prompt", None)
        metadata["classification"] = _metadata_classification(prompt, metadata)
        return replace(
            item,
            prompt=prompt or None,
            negative_prompt=negative or None,
            has_prompt=bool(prompt),
            metadata=metadata,
        )

    def _with_page_metadata_safe(self, item: AssetItem, site: str) -> AssetItem:
        """补全列表接口缺失的提示词；详情页失败时保留列表素材。"""
        try:
            return self._with_page_metadata(item, site)
        except SpiderError:
            return item

    def download(self, item: AssetItem, output_root: Path) -> DownloadResult:
        self._require_item(item)
        if not item.preview_url:
            raise SpiderError("missing_image_url", "素材缺少可下载的图片地址")
        return self._downloader.download(item.preview_url, item.id, output_root)

    @staticmethod
    def _search_parameters(
        request: SearchRequest,
    ) -> tuple[str, dict[str, object], bool]:
        filters = request.filters
        site = str(filters.get("site") or "civitai.com")
        count = filters.get("count", 12)
        count = count if isinstance(count, int) and not isinstance(count, bool) else 12
        count = max(1, min(count, 100))
        tag = filters.get("tag")
        params: dict[str, object] = {
            "query": request.query.strip(),
            "period": str(filters.get("period") or "AllTime"),
            "sort": str(filters.get("sort") or "Most Reactions"),
            "limit": count,
            "nsfw": "false" if filters.get("sfw", True) else "true",
            "tags": _TAGS.get(str(tag), tag or None),
            "cursor": request.cursor,
        }
        return site, params, bool(filters.get("only_with_prompt", False))

    @staticmethod
    def _normalize(raw: Mapping[str, Any], site: str) -> AssetItem:
        item_id = str(raw.get("id", ""))
        raw_meta = raw.get("meta")
        meta: Mapping[str, Any] = raw_meta if isinstance(raw_meta, Mapping) else {}
        prompt, negative = extract_prompts(meta)
        resources = meta.get("resources", [])
        models: list[dict[str, str]] = []
        loras: list[dict[str, str]] = []
        if isinstance(resources, list):
            for resource in resources:
                if not isinstance(resource, Mapping):
                    continue
                resource_type = str(resource.get("type", "")).lower()
                name = resource.get("name")
                if not isinstance(name, str) or not name:
                    continue
                normalized = {"type": resource_type, "name": name}
                if resource_type == "model":
                    models.append(normalized)
                elif resource_type == "lora":
                    loras.append(normalized)
        metadata: dict[str, Any] = dict(meta)
        metadata.update({"site": site, "models": models, "loras": loras})
        metadata["classification"] = _metadata_classification(prompt, meta)
        source_url = f"https://{site}/images/{item_id}" if item_id else None
        return AssetItem(
            provider="civitai",
            id=item_id,
            preview_url=str(raw["url"]) if raw.get("url") else None,
            source_url=source_url,
            author=str(raw["username"]) if raw.get("username") else None,
            created_at=str(raw["createdAt"]) if raw.get("createdAt") else None,
            width=_integer_or_none(raw.get("width")),
            height=_integer_or_none(raw.get("height")),
            has_prompt=bool(prompt),
            prompt=prompt or None,
            negative_prompt=negative or None,
            stats=dict(raw["stats"]) if isinstance(raw.get("stats"), Mapping) else {},
            metadata=metadata,
            download_mode="single",
        )

    @staticmethod
    def _cache_key(
        site: str, params: Mapping[str, object], only_with_prompt: bool
    ) -> str:
        value = {
            "site": site,
            "params": dict(params),
            "only_with_prompt": only_with_prompt,
        }
        return "civitai:" + json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )

    @staticmethod
    def _page_from_cache(value: object) -> SearchPage:
        if not isinstance(value, Mapping) or not isinstance(value.get("items"), list):
            raise SpiderError("cache_invalid", "Civitai 缓存数据无效", status=502)
        items = tuple(AssetItem.from_untrusted(item) for item in value["items"])
        cursor = value.get("next_cursor")
        return SearchPage(
            items,
            str(cursor) if cursor else None,
            stale=True,
            message="正在显示缓存结果",
        )

    @staticmethod
    def _require_item(item: AssetItem) -> None:
        if item.provider != "civitai" or not item.id.isdigit():
            raise SpiderError("invalid_asset", "Civitai 素材数据无效")


def _integer_or_none(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _metadata_classification(prompt: str, metadata: Mapping[str, Any]) -> str:
    """沿用旧节点 A/B/C 规则，同时忽略本节点附加的辅助字段。"""
    if metadata.get("workflow"):
        return "A"
    if prompt or any(
        key not in {"site", "models", "loras", "classification"} for key in metadata
    ):
        return "B"
    return "C"
