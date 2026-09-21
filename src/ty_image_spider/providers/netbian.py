"""彼岸图网壁纸来源。"""

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
from ..security import read_limited, require_https_host
from ..version import USER_AGENT
from .download_policy import HostDownloadPolicy


_ROOT = "https://pic.netbian.com"
_SAFE_ID = re.compile(r"^[0-9]+$")
_CATEGORY_PATHS = {
    "latest": ("/new/", "最新"),
    "landscape": ("/4kfengjing/", "4K风景"),
    "anime": ("/4kdongman/", "4K动漫"),
    "movie": ("/4kjuzhao/", "4K剧照"),
    "car": ("/4kqiche/", "4K汽车"),
    "animal": ("/4kdongwu/", "4K动物"),
    "background": ("/4kbeijing/", "4K背景"),
    "mobile": ("/shoujibizhi/", "4K手机"),
    "ultrawide": ("/5120x2160/", "5K带鱼屏"),
}

IMAGE_POLICY = HostDownloadPolicy(
    "netbian", lambda host: host == "pic.netbian.com", id_pattern=r"[0-9]+"
)


class Downloader(Protocol):
    def download(self, url: str, item_id: str, output_root: Path) -> DownloadResult: ...


@dataclass(frozen=True, slots=True)
class NetbianListPage:
    html: str
    current_page: int
    last_page: int


class NetbianClient:
    """只负责彼岸图网 HTML 请求，不参与素材解析。"""

    def __init__(
        self,
        open_url: Callable[..., Any] = urlopen,
        *,
        timeout_seconds: int = 30,
    ) -> None:
        self._open_url = open_url
        self._timeout_seconds = timeout_seconds

    def list(self, path: str, page: int) -> NetbianListPage:
        if page < 1:
            raise SpiderError("invalid_page", "分页必须是正整数")
        url = _page_url(path, page)
        html = self._request(url)
        last_page = _last_page(html)
        return NetbianListPage(html, page, max(page, last_page))

    def detail(self, item_id: str) -> str:
        if not _SAFE_ID.fullmatch(item_id):
            raise SpiderError("invalid_asset", "彼岸图网素材 ID 无效")
        return self._request(f"{_ROOT}/tupian/{item_id}.html")

    def _request(self, url: str) -> str:
        try:
            request = Request(url, headers={"Accept": "text/html", "User-Agent": USER_AGENT})
            with self._open_url(request, timeout=self._timeout_seconds) as response:
                require_https_host(response.geturl(), lambda host: host == "pic.netbian.com")
                return read_limited(response, 8 * 1024 * 1024).decode("utf-8", errors="replace")
        except SpiderError:
            raise
        except HTTPError as exc:
            raise SpiderError("netbian_http_error", f"彼岸图网请求失败（{exc.code}）", status=502) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise SpiderError("netbian_unavailable", "无法连接彼岸图网", status=502) from exc


class NetbianProvider:
    id = "netbian"
    image_policy = IMAGE_POLICY

    def __init__(self, client: NetbianClient, cache: JsonCache, downloader: Downloader) -> None:
        self._client = client
        self._cache = cache
        self._downloader = downloader

    def descriptor(self) -> ProviderDescriptor:
        return ProviderDescriptor(
            presentation=ProviderPresentation(
                "wallpaper", "壁纸", "B", "NETBIAN", 15, 20,
                "按当前分类新增最多100张素材，已有缓存将跳过", True,
            ),
            id=self.id,
            label="彼岸图网",
            description="浏览彼岸图网公开的中文 4K 壁纸与手机壁纸",
            filters=(FilterField(
                "category", "分类", "select", "latest",
                tuple(FilterOption(value, label) for value, (_, label) in _CATEGORY_PATHS.items()),
            ),),
            capabilities=ProviderCapabilities(bulk_download=True, pagination="page", cache=True),
            search_placeholder="按标题筛选，例如：秋日、风景",
        )

    def status(self) -> ProviderStatus:
        return ProviderStatus(True, message="公开 HTML 壁纸目录")

    def search(self, request: SearchRequest) -> SearchPage:
        category = str(request.filters.get("category") or "latest")
        path = _CATEGORY_PATHS.get(category, _CATEGORY_PATHS["latest"])[0]
        page_number = _page_number(request.cursor)
        params = {"category": category, "query": request.query.strip(), "page": page_number}
        cache_key = "netbian:" + json.dumps(params, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
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
        self._href = ""
        self._src = ""
        self._alt = ""
        self._text: list[str] = []
        self._inside_link = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "a" and (values.get("href") or "").endswith(".html"):
            self._inside_link = True
            self._href = values.get("href") or ""
            self._text = []
        elif tag == "img" and self._inside_link:
            self._src = values.get("src") or ""
            self._alt = values.get("alt") or ""

    def handle_data(self, data: str) -> None:
        if self._inside_link:
            self._text.append(data.strip())

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._inside_link:
            match = re.search(r"/(\d+)\.html$", self._href)
            if match and self._src:
                title = next((text for text in self._text if text), self._alt)
                self.items.append({"id": match.group(1), "href": self._href, "src": self._src, "alt": self._alt, "title": title})
            self._inside_link = False


class _DetailParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.preview = ""
        self.original = ""
        self.category = ""
        self.resolution = ""
        self._h1 = False
        self._category_link = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        classes = set((values.get("class") or "").split())
        if tag == "h1":
            self._h1 = True
        if tag == "img" and ("photo-pic" in classes or values.get("data-pic")):
            self.preview = values.get("src") or ""
            self.original = values.get("data-pic") or self.preview
        if tag == "a" and (values.get("href") or "").startswith("/4k"):
            self._category_link = True

    def handle_data(self, data: str) -> None:
        if self._h1:
            self.title += data.strip()
        if self._category_link:
            self.category += data.strip()
        found = re.search(r"(\d{3,5})\s*[xX×]\s*(\d{3,5})", data)
        if found:
            self.resolution = f"{found.group(1)}x{found.group(2)}"

    def handle_endtag(self, tag: str) -> None:
        if tag == "h1":
            self._h1 = False
        if tag == "a":
            self._category_link = False


def _parse_list(html: str, query: str) -> list[AssetItem]:
    parser = _ListParser()
    parser.feed(html)
    normalized_query = query.casefold()
    result: list[AssetItem] = []
    for raw in parser.items:
        haystack = f"{raw['title']} {raw['alt']}".casefold()
        if normalized_query and normalized_query not in haystack:
            continue
        result.append(AssetItem(
            provider="netbian", id=raw["id"], preview_url=urljoin(_ROOT, raw["src"]),
            source_url=urljoin(_ROOT, raw["href"]), title=raw["title"],
            metadata={"detail_path": raw["href"]},
        ))
    return result


def _parse_detail(html: str, item: AssetItem) -> AssetItem:
    parser = _DetailParser()
    parser.feed(html)
    if not parser.original:
        raise SpiderError("netbian_invalid_response", "彼岸图网详情缺少原图地址", status=502)
    resolution = re.fullmatch(r"(\d+)x(\d+)", parser.resolution)
    metadata = dict(item.metadata)
    metadata.update({
        "original_url": urljoin(_ROOT, parser.original),
        "category": parser.category,
        "resolution": parser.resolution,
    })
    return replace(
        item,
        title=parser.title or item.title,
        preview_url=urljoin(_ROOT, parser.preview) if parser.preview else item.preview_url,
        width=int(resolution.group(1)) if resolution else item.width,
        height=int(resolution.group(2)) if resolution else item.height,
        metadata=metadata,
    )


def _page_url(path: str, page: int) -> str:
    if page == 1:
        return urljoin(_ROOT, path)
    return urljoin(_ROOT, path.rstrip("/") + f"/index_{page}.html")


def _last_page(html: str) -> int:
    pages = [int(value) for value in re.findall(r"index_(\d+)\.html", html)]
    return max(pages, default=1)


def _page_number(cursor: str | None) -> int:
    try:
        return max(1, int(cursor or 1))
    except ValueError:
        return 1


def _cached_page(value: object) -> SearchPage:
    if not isinstance(value, Mapping) or not isinstance(value.get("items"), list):
        raise SpiderError("cache_invalid", "彼岸图网缓存数据无效", status=502)
    cursor = value.get("next_cursor")
    return SearchPage(tuple(AssetItem.from_untrusted(item) for item in value["items"]), str(cursor) if cursor else None, stale=True, message="正在显示缓存结果")


def _require_item(item: AssetItem) -> None:
    if item.provider != "netbian" or not _SAFE_ID.fullmatch(item.id):
        raise SpiderError("invalid_asset", "彼岸图网素材数据无效")
