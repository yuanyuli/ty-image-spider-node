"""FilmGrab 电影静帧来源。"""

from __future__ import annotations

import re
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Mapping

from ..cache import JsonCache
from ..movies.resolution import MovieResolution
from ..models import (
    AssetDetail,
    AssetItem,
    DownloadResult,
    ProviderCapabilities,
    ProviderDescriptor,
    ProviderPresentation,
    ProviderStatus,
    SearchPage,
    SearchRequest,
    SpiderError,
)
from .curated_client import FilmGrabClient
from .curated_download import CuratedDownloader
from .filmgrab_articles import FilmGrabArticles
from .film_catalog import display_film_title, film_presets, resolve_film_query


_FRAME_ID = re.compile(r"^[0-9]+-[0-9]+$")


from .download_policy import HostDownloadPolicy

IMAGE_POLICY = HostDownloadPolicy("filmgrab", lambda host: host == "film-grab.com")


class _FrameParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.frames: list[tuple[str, str, str]] = []
        self.current: tuple[str, str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "a" and "bwg-a" in (values.get("class") or "").split():
            self.current = (values.get("data-image-id") or "", values.get("href") or "")
        elif tag == "img" and self.current:
            frame_id, original = self.current
            preview = values.get("src") or ""
            if (
                frame_id.isdigit()
                and original.startswith(
                    "https://film-grab.com/wp-content/uploads/photo-gallery/"
                )
                and preview.startswith("https://film-grab.com/")
            ):
                self.frames.append((frame_id, original, preview))

    def handle_endtag(self, tag: str) -> None:
        if tag == "a":
            self.current = None


class FilmGrabProvider:
    id = "filmgrab"
    image_policy = IMAGE_POLICY

    def __init__(
        self,
        client: FilmGrabClient,
        downloader: CuratedDownloader | None = None,
        cache: JsonCache | None = None,
        movies: MovieResolution | None = None,
    ) -> None:
        self._articles = FilmGrabArticles(client, cache)
        self._downloader = downloader or CuratedDownloader(self.image_policy)
        self._movies = movies

    def descriptor(self) -> ProviderDescriptor:
        return ProviderDescriptor(
            self.id,
            "FilmGrab",
            "电影静帧画廊",
            presentation=ProviderPresentation(
                "cinema",
                "电影",
                "FILM",
                "FILMGRAB",
                40,
                10,
                "按当前搜索条件新增最多100张素材，已有缓存将跳过",
                True,
            ),
            capabilities=ProviderCapabilities(
                bulk_download=True, pagination="page", cache=True, movie_lookup=True
            ),
            search_presets=film_presets(),
            search_placeholder="中文片名，如花样年华；留空浏览全部电影",
        )

    def status(self) -> ProviderStatus:
        return ProviderStatus(True, message="公开电影静帧")

    def search(self, request: SearchRequest) -> SearchPage:
        try:
            parts = (request.cursor or "1").split(":")
            page = int(parts[0])
            offset = int(parts[1]) if len(parts) == 2 else 0
        except ValueError as exc:
            raise SpiderError("invalid_cursor", "FilmGrab 页码无效") from exc
        if page < 1 or offset < 0 or offset % 24 != 0 or len(parts) > 2:
            raise SpiderError("invalid_cursor", "FilmGrab 页码无效")
        query = request.query.strip()
        force_lookup = (
            request.filters.get("movie_lookup") is True
            or request.filters.get("tmdb_id") is not None
        )
        mapping = (
            self._movies.cached(query)
            if self._movies and not force_lookup and query
            else None
        )
        if not mapping:
            try:
                query = resolve_film_query(query)
            except SpiderError:
                if self._movies is None:
                    raise
                force_lookup = True
        if force_lookup:
            if not request.query.strip():
                raise SpiderError(
                    "movie_query_required", "请先输入电影名，再查找电影版本"
                )
            if self._movies is None:
                raise SpiderError("movie_lookup_unavailable", "扩展电影查询未配置")
            resolved = self._movies.resolve(request.query.strip(), request.filters)
            if isinstance(resolved, SearchPage):
                return resolved
            mapping = resolved
        posts, last_page, stale = self._articles.read(
            query,
            page,
            request.refresh,
            post_id=mapping["post"]["id"] if mapping else None,
        )
        items: list[AssetItem] = []
        for post in posts:
            items.extend(_post_frames(post))
        selected = items[offset : offset + 24]
        next_cursor = (
            f"{page}:{offset + 24}"
            if offset + 24 < len(items)
            else str(page + 1)
            if page < last_page
            else None
        )
        return SearchPage(
            tuple(selected),
            next_cursor,
            stale=stale,
            message="来源暂时不可用，正在显示缓存结果" if stale else "",
        )

    def detail(self, item: AssetItem) -> AssetDetail:
        _require(item)
        original = item.metadata.get("original_url")
        if not isinstance(original, str):
            raise SpiderError("invalid_asset", "FilmGrab 原图地址缺失")
        return AssetDetail(item, (original,))

    def download(self, item: AssetItem, output_root: Path) -> DownloadResult:
        _require(item)
        return self._downloader.download(
            self.detail(item).images[0], item.id, output_root
        )


def _post_frames(post: Mapping[str, Any]) -> list[AssetItem]:
    post_id = post.get("id")
    title = post.get("title")
    content = post.get("content")
    if not isinstance(post_id, int) or not isinstance(content, Mapping):
        return []
    markup = content.get("rendered")
    if not isinstance(markup, str):
        return []
    parser = _FrameParser()
    parser.feed(markup)
    name = (
        unescape(str(title.get("rendered") or "电影静帧"))
        if isinstance(title, Mapping)
        else "电影静帧"
    )
    source = str(post.get("link") or "")
    return [
        AssetItem(
            "filmgrab",
            f"{post_id}-{frame_id}",
            preview_url=preview,
            source_url=source,
            title=f"{display_film_title(name)} · {index}",
            author="FilmGrab",
            metadata={"original_url": original, "film": name},
        )
        for index, (frame_id, original, preview) in enumerate(parser.frames, 1)
    ]


def _require(item: AssetItem) -> None:
    if item.provider != "filmgrab" or not _FRAME_ID.fullmatch(item.id):
        raise SpiderError("invalid_asset", "FilmGrab 静帧 ID 无效")
