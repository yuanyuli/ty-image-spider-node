"""TMDB 电影海报与静态剧照来源。"""

from __future__ import annotations

import json
import re
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping, Protocol

from ..cache import JsonCache
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
from ..movies.tmdb import TmdbClient
from .curated_download import CuratedDownloader
from .download_policy import HostDownloadPolicy


_SAFE_ID = re.compile(r"^(\d+)-(\d+)$")
_SAFE_FILE_PATH = re.compile(r"^/[A-Za-z0-9._-]+$")
_IMAGE_ROOT = "https://image.tmdb.org"
_PAGE_SIZE = 24

IMAGE_POLICY = HostDownloadPolicy(
    "tmdb-images",
    lambda host: host == "image.tmdb.org",
    id_pattern=r"[0-9]+-[0-9]+",
)


class Downloader(Protocol):
    def download(self, url: str, item_id: str, output_root: Path) -> DownloadResult: ...


class TmdbImageProvider:
    id = "tmdb-images"
    image_policy = IMAGE_POLICY

    def __init__(
        self,
        client: TmdbClient,
        cache: JsonCache,
        downloader: Downloader | None = None,
    ) -> None:
        self._client = client
        self._cache = cache
        self._downloader = downloader or CuratedDownloader(self.image_policy)

    def descriptor(self) -> ProviderDescriptor:
        return ProviderDescriptor(
            presentation=ProviderPresentation(
                "cinema",
                "电影",
                "TMDB",
                "TMDB 电影图片",
                40,
                20,
                "按当前电影新增最多100张素材，已有缓存将跳过",
                True,
            ),
            id=self.id,
            label="TMDB 图片",
            description="按中文或英文电影名浏览 TMDB 公开海报与静态剧照",
            filters=(
                FilterField(
                    "type",
                    "图片类型",
                    "select",
                    "backdrop",
                    (
                        FilterOption("backdrop", "横幅剧照"),
                        FilterOption("poster", "海报"),
                        FilterOption("all", "全部"),
                    ),
                ),
            ),
            capabilities=ProviderCapabilities(
                bulk_download=True, pagination="page", cache=True
            ),
            search_placeholder="中文或英文电影名，例如：花样年华",
        )

    def status(self) -> ProviderStatus:
        try:
            configured = self._client.has_credentials()
        except SpiderError:
            configured = False
        if not configured:
            return ProviderStatus(
                False,
                code="tmdb_not_configured",
                message="未配置 TMDB 读取令牌",
                action="将令牌写入节点目录 .local/tmdb.json 后重试",
            )
        return ProviderStatus(True, message="TMDB 公开电影图片")

    def search(self, request: SearchRequest) -> SearchPage:
        self._require_credentials()
        movie_id = _movie_id(request.filters.get("tmdb_id"))
        query = request.query.strip()
        movie: Mapping[str, Any]
        if movie_id is None:
            if not query:
                raise SpiderError("tmdb_query_required", "请输入电影名后再搜索 TMDB 图片")
            candidates = self._client.search(query)
            if not candidates:
                raise SpiderError("tmdb_movie_not_found", "TMDB 没有找到匹配的电影")
            movie = candidates[0]
            movie_id = _movie_id(movie.get("id"))
            if movie_id is None:
                raise SpiderError("tmdb_invalid_response", "TMDB 返回的电影 ID 无效", status=502)
        else:
            movie = self._client.movie(movie_id)
            query = str(movie.get("title") or query)

        kind = str(request.filters.get("type") or "backdrop")
        if kind not in {"backdrop", "poster", "all"}:
            kind = "backdrop"
        cached = self._cache.get(_cache_key(movie_id, kind), max_age_seconds=86400)
        if isinstance(cached, Mapping) and isinstance(cached.get("items"), list):
            gallery = cached
        else:
            gallery = self._load_gallery(movie_id, movie, kind)
            self._cache.put(_cache_key(movie_id, kind), gallery)

        raw_items = gallery.get("items")
        if not isinstance(raw_items, list):
            raise SpiderError("tmdb_invalid_response", "TMDB 图片缓存无效", status=502)
        page = _page_number(request.cursor)
        start = (page - 1) * _PAGE_SIZE
        selected = tuple(
            AssetItem.from_untrusted(item)
            for item in raw_items[start : start + _PAGE_SIZE]
        )
        next_cursor = str(page + 1) if start + _PAGE_SIZE < len(raw_items) else None
        return SearchPage(selected, next_cursor)

    def detail(self, item: AssetItem) -> AssetDetail:
        verified = self._verified_item(item)
        original = str(verified.metadata["original_url"])
        return AssetDetail(verified, (original,), metadata=verified.metadata)

    def download(self, item: AssetItem, output_root: Path) -> DownloadResult:
        verified = self._verified_item(item)
        return self._downloader.download(
            str(verified.metadata["original_url"]), verified.id, output_root
        )

    def _load_gallery(
        self, movie_id: int, movie: Mapping[str, Any], kind: str
    ) -> dict[str, Any]:
        rows = self._client.images(movie_id)
        items: list[dict[str, Any]] = []
        for index, raw in enumerate(rows):
            if not isinstance(raw, Mapping):
                continue
            media_type = str(raw.get("type") or "")
            if kind != "all" and media_type != kind:
                continue
            file_path = raw.get("file_path")
            width = raw.get("width")
            height = raw.get("height")
            if (
                not isinstance(file_path, str)
                or not _SAFE_FILE_PATH.fullmatch(file_path)
                or not isinstance(width, int)
                or isinstance(width, bool)
                or not isinstance(height, int)
                or isinstance(height, bool)
                or width < 1
                or height < 1
            ):
                continue
            item_id = f"{movie_id}-{index}"
            title = str(movie.get("title") or movie.get("original_title") or "未命名电影")
            items.append(
                AssetItem(
                    provider=self.id,
                    id=item_id,
                    preview_url=f"{_IMAGE_ROOT}/t/p/w780{file_path}",
                    source_url=f"https://www.themoviedb.org/movie/{movie_id}",
                    title=title,
                    created_at=str(movie.get("year") or "") or None,
                    width=width,
                    height=height,
                    tags=(media_type,),
                    metadata={
                        "movie_id": movie_id,
                        "file_path": file_path,
                        "media_type": media_type,
                        "original_url": f"{_IMAGE_ROOT}/t/p/original{file_path}",
                        "original_title": str(movie.get("original_title") or ""),
                    },
                ).to_dict()
            )
        return {"movie": dict(movie), "items": items}

    def _verified_item(self, item: AssetItem) -> AssetItem:
        match = _SAFE_ID.fullmatch(item.id)
        if item.provider != self.id or not match:
            raise SpiderError("invalid_asset", "TMDB 图片素材数据无效")
        movie_id = int(match.group(1))
        index = int(match.group(2))
        file_path = item.metadata.get("file_path")
        if not isinstance(file_path, str) or not _SAFE_FILE_PATH.fullmatch(file_path):
            raise SpiderError("invalid_asset", "TMDB 图片路径无效")
        rows = self._client.images(movie_id)
        if index >= len(rows) or not isinstance(rows[index], Mapping):
            raise SpiderError("invalid_asset", "TMDB 图片不存在")
        verified_path = rows[index].get("file_path")
        if verified_path != file_path:
            raise SpiderError("invalid_asset", "TMDB 图片路径不匹配")
        width = rows[index].get("width")
        height = rows[index].get("height")
        if not isinstance(width, int) or not isinstance(height, int):
            raise SpiderError("tmdb_invalid_response", "TMDB 图片尺寸无效", status=502)
        metadata = dict(item.metadata)
        metadata.update(
            {
                "movie_id": movie_id,
                "file_path": file_path,
                "original_url": f"{_IMAGE_ROOT}/t/p/original{file_path}",
            }
        )
        return replace(item, width=width, height=height, metadata=metadata)

    def _require_credentials(self) -> None:
        try:
            configured = self._client.has_credentials()
        except SpiderError as exc:
            raise exc
        if not configured:
            raise SpiderError(
                "tmdb_not_configured",
                "扩展 TMDB 图片需要配置读取令牌",
                action="将令牌写入节点目录 .local/tmdb.json 后重试",
            )


def _movie_id(value: object) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return None


def _page_number(cursor: str | None) -> int:
    try:
        return max(1, int(cursor or 1))
    except ValueError:
        return 1


def _cache_key(movie_id: int, kind: str) -> str:
    return "tmdb-images:" + json.dumps(
        {"movie_id": movie_id, "type": kind},
        sort_keys=True,
        separators=(",", ":"),
    )
