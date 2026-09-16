"""Civitai 素材来源策略。"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping

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


class CivitaiProvider:
    id = "civitai"

    def __init__(
        self, client: CivitaiClient, cache: JsonCache, downloader: ImageDownloader
    ) -> None:
        self._client = client
        self._cache = cache
        self._downloader = downloader

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
            capabilities=ProviderCapabilities(bulk_download=True),
        )

    def status(self) -> ProviderStatus:
        return ProviderStatus(True)

    def search(self, request: SearchRequest) -> SearchPage:
        site, params, only_with_prompt = self._search_parameters(request)
        cache_key = self._cache_key(site, params, only_with_prompt)
        try:
            raw_page = self._client.search(site, params)
            page = SearchPage(
                tuple(
                    item
                    for item in (self._normalize(raw, site) for raw in raw_page.items)
                    if not only_with_prompt or item.has_prompt
                ),
                raw_page.next_cursor,
            )
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
            "nsfw": "None" if filters.get("sfw", True) else None,
            "tag": _TAGS.get(str(tag), tag or None),
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
