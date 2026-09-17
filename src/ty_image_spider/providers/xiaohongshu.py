"""基于 OpenCLI 的可选小红书素材来源策略。"""

from __future__ import annotations

import hashlib
import re
from contextlib import AbstractContextManager
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping, Protocol
from urllib.parse import urlparse, urlsplit, urlunsplit

from PIL import Image

from ..cache import JsonCache
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
from ..opencli import OpenCliRunner
from ..security import resolve_inside
from .xiaohongshu_extract import (
    build_card_extract_js,
    build_detail_extract_js,
    detail_note_id,
    merge_search_rows,
    trusted_images,
)


_SAFE_NOTE_ID = re.compile(r"^[0-9a-zA-Z_-]{1,64}$")
_NOTE_PATH = re.compile(r"^/(?:explore|search_result|note)/([0-9a-zA-Z_-]+)/*$")
_IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp", ".gif"})


class SessionLock(Protocol):
    def __enter__(self) -> AbstractContextManager[Any] | None: ...

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> object: ...


class XiaohongshuProvider:
    id = "xiaohongshu"

    def __init__(
        self,
        runner: OpenCliRunner,
        cache: JsonCache,
        session_lock: SessionLock,
    ) -> None:
        self._runner = runner
        self._cache = cache
        self._session_lock = session_lock

    def descriptor(self) -> ProviderDescriptor:
        return ProviderDescriptor(
            id=self.id,
            label="小红书",
            description="通过 OpenCLI 与已登录的 Chrome 浏览公开笔记图片",
            filters=(
                FilterField(
                    "sort",
                    "排序",
                    "select",
                    "comprehensive",
                    tuple(
                        FilterOption(value, label)
                        for value, label in (
                            ("comprehensive", "综合"),
                            ("latest", "最新"),
                            ("most-liked", "最多点赞"),
                            ("most-commented", "最多评论"),
                            ("most-collected", "最多收藏"),
                        )
                    ),
                ),
                FilterField(
                    "note_type",
                    "笔记类型",
                    "select",
                    "image",
                    (FilterOption("image", "图文"), FilterOption("all", "不限")),
                ),
                FilterField(
                    "publish_time",
                    "发布时间",
                    "select",
                    "anytime",
                    tuple(
                        FilterOption(value, label)
                        for value, label in (
                            ("anytime", "不限"),
                            ("day", "一天内"),
                            ("week", "一周内"),
                            ("half-year", "半年内"),
                        )
                    ),
                ),
                FilterField("count", "数量", "number", 12, minimum=1, maximum=50),
            ),
            capabilities=ProviderCapabilities(bulk_download=False, pagination="none"),
        )

    def status(self) -> ProviderStatus:
        try:
            version = self._runner.version()
            self._runner.bridge_status()
            return ProviderStatus(True, message=f"OpenCLI {version} 已连接")
        except SpiderError as exc:
            return ProviderStatus(False, exc.code, exc.message, exc.action)

    def search(self, request: SearchRequest) -> SearchPage:
        query = request.query.strip()
        mode = _classify_query(query)
        if mode == "invalid_url":
            raise SpiderError(
                "invalid_note_url",
                "小红书链接无效",
                "请使用包含 xsec_token 的完整笔记链接或 xhslink 短链接",
            )
        if mode == "note":
            detail = self._read_note(query, _note_id(query))
            return SearchPage((detail.item,))
        if not query:
            return SearchPage(())
        return self._search_keyword(request, query)

    def detail(self, item: AssetItem) -> AssetDetail:
        self._require_item(item)
        if not item.source_url or _classify_query(item.source_url) != "note":
            raise SpiderError(
                "signed_note_url_required",
                "查看小红书详情需要完整签名链接",
                "请重新搜索这篇笔记",
            )
        return self._read_note(item.source_url, item.id, base_item=item)

    def download(self, item: AssetItem, output_root: Path) -> DownloadResult:
        self._require_item(item)
        if not item.source_url or _classify_query(item.source_url) != "note":
            raise SpiderError(
                "signed_note_url_required", "下载小红书笔记需要完整签名链接"
            )
        target = resolve_inside(
            output_root, Path("ty-image-spider/xiaohongshu") / item.id
        )
        before = _snapshot_images(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        with self._session_lock:
            self._runner.run_json(
                [
                    "xiaohongshu",
                    "download",
                    item.source_url,
                    "--output",
                    str(target.parent),
                    "--format",
                    "json",
                    "--site-session",
                    "persistent",
                    "--window",
                    "background",
                ],
                timeout_seconds=180,
            )
        return _verified_new_images(target, before, Path(output_root))

    def _search_keyword(self, request: SearchRequest, query: str) -> SearchPage:
        filters = request.filters
        count = filters.get("count", 12)
        count = count if isinstance(count, int) and not isinstance(count, bool) else 12
        count = max(1, min(count, 50))
        sort = str(filters.get("sort") or "comprehensive")
        note_type = str(filters.get("note_type") or "image")
        publish_time = str(filters.get("publish_time") or "anytime")
        cache_key = _cache_key(query, sort, note_type, publish_time, count)
        try:
            with self._session_lock:
                rows = self._runner.run_json(
                    [
                        "xiaohongshu",
                        "search",
                        query,
                        "--site-session",
                        "persistent",
                        "--window",
                        "background",
                        "--limit",
                        str(count),
                        "--sort",
                        sort,
                        "--note-type",
                        note_type,
                        "--publish-time",
                        publish_time,
                        "--format",
                        "json",
                    ],
                    timeout_seconds=120,
                )
                cards = self._runner.run_json(
                    [
                        "browser",
                        "site:xiaohongshu",
                        "eval",
                        build_card_extract_js(),
                        "--format",
                        "json",
                    ],
                    timeout_seconds=30,
                )
            items = tuple(
                _search_item(value) for value in merge_search_rows(rows, cards)
            )
            page = SearchPage(items)
            self._cache.put(cache_key, _persistent_page(page))
            return page
        except SpiderError:
            cached = self._cache.get(cache_key, max_age_seconds=300)
            if cached is None:
                raise
            return _cached_page(cached)

    def _read_note(
        self, url: str, fallback_id: str, base_item: AssetItem | None = None
    ) -> AssetDetail:
        with self._session_lock:
            rows = self._runner.run_json(
                [
                    "xiaohongshu",
                    "note",
                    url,
                    "--format",
                    "json",
                    "--site-session",
                    "persistent",
                    "--window",
                    "background",
                ],
                timeout_seconds=120,
            )
            browser = self._runner.run_json(
                [
                    "browser",
                    "site:xiaohongshu",
                    "eval",
                    build_detail_extract_js(fallback_id),
                    "--format",
                    "json",
                ],
                timeout_seconds=30,
            )
        fields = _detail_fields(rows)
        images = trusted_images(browser)
        note_id = detail_note_id(browser, fallback_id)
        if not _SAFE_NOTE_ID.fullmatch(note_id):
            raise SpiderError("invalid_note", "小红书笔记 ID 无效", status=502)
        stats = {
            key: fields[key]
            for key in ("likes", "collects", "comments")
            if fields.get(key) is not None
        }
        tags = tuple(
            part.strip() for part in fields.get("tags", "").split(",") if part.strip()
        )
        item = AssetItem(
            provider=self.id,
            id=note_id,
            preview_url=images[0]
            if images
            else (base_item.preview_url if base_item else None),
            source_url=url,
            title=fields.get("title") or (base_item.title if base_item else None),
            author=fields.get("author") or (base_item.author if base_item else None),
            image_count=max(1, len(images)),
            stats=stats or (base_item.stats if base_item else {}),
            tags=tags or (base_item.tags if base_item else ()),
            metadata={"opencli": "xiaohongshu"},
            download_mode="note",
        )
        return AssetDetail(
            item, images, fields.get("content", ""), metadata={"tags": list(item.tags)}
        )

    @staticmethod
    def _require_item(item: AssetItem) -> None:
        if item.provider != "xiaohongshu" or not _SAFE_NOTE_ID.fullmatch(item.id):
            raise SpiderError("invalid_asset", "小红书素材数据无效")


def _search_item(value: Mapping[str, Any]) -> AssetItem:
    return AssetItem(
        provider="xiaohongshu",
        id=str(value["id"]),
        preview_url=value.get("preview_url"),
        source_url=value.get("source_url"),
        title=value.get("title"),
        author=value.get("author"),
        created_at=value.get("created_at"),
        image_count=int(value.get("image_count", 1)),
        stats={"likes": str(value.get("likes", "0"))},
        metadata={"opencli": "xiaohongshu"},
        download_mode="note",
    )


def _detail_fields(value: object) -> dict[str, str]:
    if isinstance(value, Mapping) and "data" in value:
        value = value["data"]
    result: dict[str, str] = {}
    if not isinstance(value, list):
        return result
    for row in value:
        if not isinstance(row, Mapping):
            continue
        field = row.get("field")
        raw = row.get("value")
        if isinstance(field, str) and isinstance(raw, str):
            result[field] = raw.strip()
    return result


def _classify_query(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        return "keyword"
    host = (parsed.hostname or "").lower()
    if parsed.scheme == "https" and host in {"xhslink.com", "www.xhslink.com"}:
        return "note"
    trusted_host = host == "xiaohongshu.com" or host.endswith(".xiaohongshu.com")
    signed = bool(parsed.query and "xsec_token=" in parsed.query)
    if (
        parsed.scheme == "https"
        and trusted_host
        and _NOTE_PATH.fullmatch(parsed.path)
        and signed
    ):
        return "note"
    return "invalid_url"


def _note_id(url: str) -> str:
    matched = _NOTE_PATH.fullmatch(urlparse(url).path)
    if matched:
        return matched.group(1)
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]


def _cache_key(
    query: str, sort: str, note_type: str, publish_time: str, count: int
) -> str:
    raw = "\0".join((query, sort, note_type, publish_time, str(count)))
    return "xiaohongshu:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _persistent_page(page: SearchPage) -> dict[str, object]:
    items = []
    for item in page.items:
        preview = _without_query(item.preview_url) if item.preview_url else None
        items.append(replace(item, preview_url=preview, source_url=None).to_dict())
    return {"items": items}


def _without_query(url: str) -> str:
    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def _cached_page(value: object) -> SearchPage:
    if not isinstance(value, Mapping) or not isinstance(value.get("items"), list):
        raise SpiderError("cache_invalid", "小红书缓存数据无效", status=502)
    items = tuple(AssetItem.from_untrusted(item) for item in value["items"])
    return SearchPage(
        items, stale=True, message="正在显示短期缓存结果，请重新搜索后查看详情"
    )


def _snapshot_images(directory: Path) -> set[Path]:
    if not directory.is_dir():
        return set()
    return {
        path.resolve()
        for path in directory.rglob("*")
        if path.is_file()
        and not path.is_symlink()
        and path.suffix.casefold() in _IMAGE_EXTENSIONS
    }


def _verified_new_images(
    directory: Path, before: set[Path], output_root: Path
) -> DownloadResult:
    root = output_root.resolve()
    verified: list[str] = []
    if directory.is_dir():
        for path in sorted(directory.rglob("*")):
            try:
                resolved = path.resolve(strict=True)
                resolved.relative_to(root)
                if resolved in before or path.is_symlink() or not path.is_file():
                    continue
                if path.suffix.casefold() not in _IMAGE_EXTENSIONS:
                    continue
                with Image.open(resolved) as image:
                    image.verify()
                verified.append(resolved.relative_to(root).as_posix())
            except (OSError, ValueError):
                continue
    if not verified:
        raise SpiderError("download_empty", "OpenCLI 未生成有效的新图片", status=502)
    return DownloadResult(tuple(verified), f"已下载 {len(verified)} 张图片")
