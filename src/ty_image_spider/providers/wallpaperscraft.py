"""WallpapersCraft 壁纸来源。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from gzip import GzipFile
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import Request, urlopen

from ..infrastructure.cache import JsonCache
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
from ..infrastructure.security import read_limited, require_https_host
from ..version import USER_AGENT
from .shared import HostDownloadPolicy


_ROOT = "https://wallpaperscraft.com"
_MAX_HTML_BYTES = 8 * 1024 * 1024
_SAFE_PATH = re.compile(r"^/download/[a-z0-9_-]+_([0-9]+)/([0-9]+x[0-9]+)$")
_SAFE_ID = re.compile(r"^[0-9]+-[0-9]+x[0-9]+$")
_CATEGORIES = {
    "nature": "自然",
    "city": "城市",
    "abstract": "抽象",
    "space": "太空",
    "anime": "动漫",
    "animals": "动物",
    "cars": "汽车",
    "minimalism": "极简",
}
_RESOLUTIONS = ("1920x1080", "2560x1440", "3840x2160", "3440x1440")

IMAGE_POLICY = HostDownloadPolicy(
    "wallpaperscraft",
    lambda host: host == "images.wallpaperscraft.com",
    id_pattern=r"[0-9]+-[0-9]+x[0-9]+",
)


class Downloader(Protocol):
    def download(self, url: str, item_id: str, output_root: Path) -> DownloadResult: ...


@dataclass(frozen=True, slots=True)
class WallpapersCraftPage:
    html: str
    current_page: int
    last_page: int


class WallpapersCraftClient:
    def __init__(self, open_url: Callable[..., Any] = urlopen) -> None:
        self._open_url = open_url

    def list(
        self, category: str, resolution: str, query: str, page: int
    ) -> WallpapersCraftPage:
        if category not in _CATEGORIES or resolution not in _RESOLUTIONS or page < 1:
            raise SpiderError("invalid_filter", "WallpapersCraft 筛选条件无效")
        if query:
            params = {"query": query, "size": resolution}
            if page > 1:
                params["page"] = str(page)
            url = f"{_ROOT}/search/?{urlencode(params)}"
        else:
            suffix = f"/page{page}" if page > 1 else ""
            url = f"{_ROOT}/catalog/{category}/{resolution}{suffix}"
        html = self._read(url)
        pages = [
            int(value)
            for value in re.findall(r"(?:page|[?&]page=)(\d+)", html)
        ]
        return WallpapersCraftPage(html, page, max([page, *pages]))

    def detail(self, path: str) -> str:
        if not _SAFE_PATH.fullmatch(path):
            raise SpiderError("invalid_asset", "WallpapersCraft 详情地址无效")
        return self._read(urljoin(_ROOT, path))

    def _read(self, url: str) -> str:
        request = Request(
            url,
            headers={"Accept": "text/html", "User-Agent": "Mozilla/5.0 " + USER_AGENT},
        )
        try:
            with self._open_url(request, timeout=30) as response:
                require_https_host(
                    response.geturl(),
                    lambda host: host
                    in {"wallpaperscraft.com", "www.wallpaperscraft.com"},
                )
                payload = read_limited(response, _MAX_HTML_BYTES)
                if response.headers.get("Content-Encoding", "").lower() == "gzip":
                    with GzipFile(fileobj=BytesIO(payload)) as compressed:
                        payload = compressed.read(_MAX_HTML_BYTES + 1)
                    if len(payload) > _MAX_HTML_BYTES:
                        raise SpiderError(
                            "response_too_large", "WallpapersCraft 页面超过大小限制"
                        )
                return payload.decode("utf-8", errors="replace")
        except SpiderError:
            raise
        except HTTPError as exc:
            raise SpiderError(
                "wallpaperscraft_http_error",
                f"WallpapersCraft 请求失败（{exc.code}）",
                status=502,
            ) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise SpiderError(
                "wallpaperscraft_unavailable", "无法连接 WallpapersCraft", status=502
            ) from exc


class WallpapersCraftProvider:
    id = "wallpaperscraft"
    image_policy = IMAGE_POLICY

    def __init__(
        self,
        client: WallpapersCraftClient,
        cache: JsonCache,
        downloader: Downloader,
    ) -> None:
        self._client = client
        self._cache = cache
        self._downloader = downloader

    def descriptor(self) -> ProviderDescriptor:
        return ProviderDescriptor(
            presentation=ProviderPresentation(
                "wallpaper",
                "壁纸",
                "WC",
                "WALLPAPERSCRAFT",
                15,
                40,
                "按当前分类新增最多100张素材，已有缓存将跳过",
                True,
            ),
            id=self.id,
            label="WallpapersCraft",
            description="浏览 WallpapersCraft 公开桌面壁纸",
            filters=(
                FilterField(
                    "category",
                    "分类",
                    "select",
                    "nature",
                    tuple(
                        FilterOption(key, label) for key, label in _CATEGORIES.items()
                    ),
                ),
                FilterField(
                    "resolution",
                    "分辨率",
                    "select",
                    "1920x1080",
                    tuple(FilterOption(value, value) for value in _RESOLUTIONS),
                ),
            ),
            capabilities=ProviderCapabilities(
                bulk_download=True, pagination="page", cache=True
            ),
            search_placeholder="可留空浏览分类；关键词建议使用英文",
        )

    def status(self) -> ProviderStatus:
        return ProviderStatus(True, message="公开壁纸目录")

    def search(self, request: SearchRequest) -> SearchPage:
        category = str(request.filters.get("category") or "nature")
        resolution = str(request.filters.get("resolution") or "1920x1080")
        if category not in _CATEGORIES:
            category = "nature"
        if resolution not in _RESOLUTIONS:
            resolution = "1920x1080"
        page_number = _page_number(request.cursor)
        query = request.query.strip()
        cache_key = "wallpaperscraft:" + json.dumps(
            {
                "category": category,
                "resolution": resolution,
                "query": query,
                "page": page_number,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        try:
            raw = self._client.list(category, resolution, query, page_number)
            page = SearchPage(
                tuple(_parse_list(raw.html)),
                str(page_number + 1) if page_number < raw.last_page else None,
            )
            self._cache.put(cache_key, page.to_dict())
            return page
        except SpiderError:
            cached = self._cache.get(cache_key, max_age_seconds=None)
            if not isinstance(cached, Mapping) or not isinstance(
                cached.get("items"), list
            ):
                raise
            cursor = cached.get("next_cursor")
            return SearchPage(
                tuple(AssetItem.from_untrusted(item) for item in cached["items"]),
                str(cursor) if cursor else None,
                stale=True,
                message="正在显示缓存结果",
            )

    def detail(self, item: AssetItem) -> AssetDetail:
        _require_item(item)
        path = item.metadata.get("detail_path")
        if not isinstance(path, str) or not _SAFE_PATH.fullmatch(path):
            raise SpiderError("invalid_asset", "WallpapersCraft 详情地址无效")
        original = _parse_original(self._client.detail(path), item)
        metadata = {**item.metadata, "original_url": original}
        enriched = replace(item, metadata=metadata)
        return AssetDetail(enriched, (original,), metadata=metadata)

    def download(self, item: AssetItem, output_root: Path) -> DownloadResult:
        verified = self.detail(item).item
        return self._downloader.download(
            str(verified.metadata["original_url"]), verified.id, output_root
        )


class _ListParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.items: list[dict[str, str]] = []
        self._path = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "a" and "wallpapers__link" in (values.get("class") or "").split():
            self._path = values.get("href") or ""
        elif tag == "img" and self._path and "wallpapers__image" in (
            values.get("class") or ""
        ).split():
            self.items.append(
                {
                    "path": self._path,
                    "preview": values.get("src") or "",
                    "alt": values.get("alt") or "",
                }
            )

    def handle_endtag(self, tag: str) -> None:
        if tag == "a":
            self._path = ""


def _parse_list(html: str) -> list[AssetItem]:
    parser = _ListParser()
    parser.feed(html)
    result: list[AssetItem] = []
    for raw in parser.items:
        match = _SAFE_PATH.fullmatch(raw["path"])
        preview = raw["preview"]
        if not match or urlsplit(preview).hostname != "images.wallpaperscraft.com":
            continue
        width, height = (int(value) for value in match.group(2).split("x"))
        title = re.sub(r"^Preview wallpaper\s*", "", raw["alt"], flags=re.I)
        result.append(
            AssetItem(
                provider="wallpaperscraft",
                id=f"{match.group(1)}-{match.group(2)}",
                preview_url=preview,
                source_url=urljoin(_ROOT, raw["path"]),
                title=title,
                width=width,
                height=height,
                metadata={"detail_path": raw["path"], "resolution": match.group(2)},
            )
        )
    return result


def _parse_original(html: str, item: AssetItem) -> str:
    path = item.metadata.get("detail_path")
    match = _SAFE_PATH.fullmatch(str(path))
    if not match:
        raise SpiderError("invalid_asset", "WallpapersCraft 素材数据无效")
    expected_suffix = f"_{match.group(1)}_{match.group(2)}.jpg"
    urls = re.findall(
        r'https://images\.wallpaperscraft\.com/image/single/[^"\'<> ]+', html
    )
    original = next(
        (url for url in urls if urlsplit(url).path.endswith(expected_suffix)), ""
    )
    if not original:
        raise SpiderError(
            "wallpaperscraft_invalid_response",
            "WallpapersCraft 详情缺少原图",
            status=502,
        )
    IMAGE_POLICY.validate_url(original)
    return original


def _page_number(cursor: str | None) -> int:
    try:
        return max(1, int(cursor or 1))
    except ValueError:
        return 1


def _require_item(item: AssetItem) -> None:
    if item.provider != "wallpaperscraft" or not _SAFE_ID.fullmatch(item.id):
        raise SpiderError("invalid_asset", "WallpapersCraft 素材数据无效")
