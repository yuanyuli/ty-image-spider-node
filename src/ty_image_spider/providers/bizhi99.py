"""壁纸网（bizhi99.com）来源。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
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
from .download_policy import HostDownloadPolicy


_ROOT = "https://www.bizhi99.com"
_IMAGE_ROOT = "https://pic.bizhi66.com"
_SAFE_ID = re.compile(r"^[0-9]+$")
_CATEGORY_PATHS = {
    "latest": ("/zuixin/", "最新"),
    "landscape": ("/c2/", "风景美图"),
    "stars": ("/c18/", "星空壁纸"),
    "anime": ("/c3/", "动漫壁纸"),
    "background": ("/c21/", "背景壁纸"),
    "animal": ("/c4/", "萌宠动物"),
    "car": ("/c5/", "汽车天下"),
    "movie": ("/s/1842/", "影视剧照"),
    "ultrawide": ("/3440x1440/", "带鱼屏"),
    "4k": ("/3840x2160/", "4K壁纸"),
}

IMAGE_POLICY = HostDownloadPolicy(
    "bizhi99", lambda host: host == "pic.bizhi66.com", id_pattern=r"[0-9]+"
)


class Downloader(Protocol):
    def download(self, url: str, item_id: str, output_root: Path) -> DownloadResult: ...


@dataclass(frozen=True, slots=True)
class Bizhi99ListPage:
    html: str
    current_page: int
    last_page: int


class Bizhi99Client:
    """只负责壁纸网页面请求。"""

    def __init__(self, open_url: Callable[..., Any] = urlopen, *, timeout_seconds: int = 30) -> None:
        self._open_url = open_url
        self._timeout_seconds = timeout_seconds

    def list(self, path: str, page: int) -> Bizhi99ListPage:
        if page < 1:
            raise SpiderError("invalid_page", "分页必须是正整数")
        html = self._request(_page_url(path, page))
        page_prefix = re.escape(path.rstrip("/"))
        pages = [
            int(value)
            for value in re.findall(rf"{page_prefix}/(\d+)\.html", html)
        ]
        return Bizhi99ListPage(html, page, max([page, *pages]))

    def detail(self, item_id: str) -> str:
        if not _SAFE_ID.fullmatch(item_id):
            raise SpiderError("invalid_asset", "壁纸网素材 ID 无效")
        return self._request(f"{_ROOT}/bizhi/{item_id}.html")

    def _request(self, url: str) -> str:
        try:
            request = Request(url, headers={"Accept": "text/html", "User-Agent": USER_AGENT})
            with self._open_url(request, timeout=self._timeout_seconds) as response:
                require_https_host(response.geturl(), lambda host: host in {"www.bizhi99.com", "bizhi99.com"})
                return read_limited(response, 8 * 1024 * 1024).decode("utf-8", errors="replace")
        except SpiderError:
            raise
        except HTTPError as exc:
            raise SpiderError("bizhi99_http_error", f"壁纸网请求失败（{exc.code}）", status=502) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise SpiderError("bizhi99_unavailable", "无法连接壁纸网", status=502) from exc


class Bizhi99Provider:
    id = "bizhi99"
    image_policy = IMAGE_POLICY

    def __init__(self, client: Bizhi99Client, cache: JsonCache, downloader: Downloader) -> None:
        self._client = client
        self._cache = cache
        self._downloader = downloader

    def descriptor(self) -> ProviderDescriptor:
        return ProviderDescriptor(
            presentation=ProviderPresentation(
                "wallpaper", "壁纸", "B", "BIZHI99", 15, 30,
                "按当前分类新增最多100张素材，已有缓存将跳过", True,
            ),
            id=self.id,
            label="壁纸网",
            description="浏览壁纸网公开的中文 4K、5K 和带鱼屏壁纸",
            filters=(FilterField(
                "category", "分类", "select", "latest",
                tuple(FilterOption(value, label) for value, (_, label) in _CATEGORY_PATHS.items()),
            ),),
            capabilities=ProviderCapabilities(bulk_download=True, pagination="page", cache=True),
            search_placeholder="按标题筛选，例如：风景、电影、动漫",
        )

    def status(self) -> ProviderStatus:
        return ProviderStatus(True, message="公开 HTML 壁纸目录")

    def search(self, request: SearchRequest) -> SearchPage:
        category = str(request.filters.get("category") or "latest")
        path = _CATEGORY_PATHS.get(category, _CATEGORY_PATHS["latest"])[0]
        page_number = _page_number(request.cursor)
        params = {"category": category, "query": request.query.strip(), "page": page_number}
        cache_key = "bizhi99:" + json.dumps(params, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        try:
            raw = self._client.list(path, page_number)
            items = tuple(_parse_list(raw.html, request.query.strip()))
            next_cursor = str(page_number + 1) if page_number < raw.last_page else None
            page = SearchPage(items, next_cursor)
            self._cache.put(cache_key, page.to_dict())
            return page
        except SpiderError:
            cached = self._cache.get(cache_key, max_age_seconds=None)
            if cached is None:
                raise
            return _cached_page(cached)

    def detail(self, item: AssetItem) -> AssetDetail:
        _require_item(item)
        parsed = _parse_detail(self._client.detail(item.id), item)
        return AssetDetail(parsed, (str(parsed.metadata["original_url"]),), metadata=parsed.metadata)

    def download(self, item: AssetItem, output_root: Path) -> DownloadResult:
        _require_item(item)
        verified = self.detail(item).item
        return self._downloader.download(str(verified.metadata["original_url"]), verified.id, output_root)


class _ListParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.items: list[dict[str, str]] = []
        self._link: dict[str, str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "a" and (values.get("href") or "").startswith("/bizhi/"):
            self._link = {"href": values.get("href") or "", "title": values.get("title") or ""}
        elif tag == "img" and self._link is not None:
            self._link["preview"] = values.get("data-original") or values.get("src") or ""
            self._link["alt"] = values.get("alt") or ""

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._link is not None:
            match = re.fullmatch(r"/bizhi/(\d+)\.html", self._link.get("href", ""))
            if match and self._link.get("preview"):
                self.items.append({**self._link, "id": match.group(1)})
            self._link = None


class _DetailParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.original = ""
        self.resolution = ""
        self._h1 = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "h1":
            self._h1 = True
        if tag == "img" and not self.original:
            source = values.get("src") or ""
            if source.startswith(_IMAGE_ROOT + "/pic/"):
                self.original = source.split("?", 1)[0]

    def handle_data(self, data: str) -> None:
        if self._h1:
            self.title += data.strip()
        found = re.search(r"(\d{3,5})\s*[xX×]\s*(\d{3,5})", data)
        if found:
            self.resolution = f"{found.group(1)}x{found.group(2)}"

    def handle_endtag(self, tag: str) -> None:
        if tag == "h1":
            self._h1 = False


def _parse_list(html: str, query: str) -> list[AssetItem]:
    parser = _ListParser()
    parser.feed(html)
    normalized_query = query.casefold()
    result: list[AssetItem] = []
    for raw in parser.items:
        title = raw.get("title") or raw.get("alt") or ""
        if normalized_query and normalized_query not in title.casefold():
            continue
        result.append(AssetItem(
            provider="bizhi99", id=raw["id"], preview_url=raw["preview"],
            source_url=urljoin(_ROOT, raw["href"]), title=title,
            metadata={"detail_path": raw["href"]},
        ))
    return result


def _parse_detail(html: str, item: AssetItem) -> AssetItem:
    parser = _DetailParser()
    parser.feed(html)
    if not parser.original:
        raise SpiderError("bizhi99_invalid_response", "壁纸网详情缺少原图地址", status=502)
    resolution = re.fullmatch(r"(\d+)x(\d+)", parser.resolution)
    metadata = dict(item.metadata)
    metadata["original_url"] = parser.original
    metadata["resolution"] = parser.resolution
    return replace(
        item,
        title=parser.title or item.title,
        width=int(resolution.group(1)) if resolution else item.width,
        height=int(resolution.group(2)) if resolution else item.height,
        metadata=metadata,
    )


def _page_url(path: str, page: int) -> str:
    if page == 1:
        return urljoin(_ROOT, path)
    return urljoin(_ROOT, path.rstrip("/") + f"/{page}.html")


def _page_number(cursor: str | None) -> int:
    try:
        return max(1, int(cursor or 1))
    except ValueError:
        return 1


def _cached_page(value: object) -> SearchPage:
    if not isinstance(value, Mapping) or not isinstance(value.get("items"), list):
        raise SpiderError("cache_invalid", "壁纸网缓存数据无效", status=502)
    cursor = value.get("next_cursor")
    return SearchPage(tuple(AssetItem.from_untrusted(item) for item in value["items"]), str(cursor) if cursor else None, stale=True, message="正在显示缓存结果")


def _require_item(item: AssetItem) -> None:
    if item.provider != "bizhi99" or not _SAFE_ID.fullmatch(item.id):
        raise SpiderError("invalid_asset", "壁纸网素材数据无效")
