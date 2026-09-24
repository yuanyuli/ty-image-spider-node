"""彼岸图网 HTML 的纯解析函数。"""

import re
from dataclasses import replace
from html.parser import HTMLParser
from urllib.parse import urljoin

from ....domain import AssetItem, SpiderError

_ROOT = "https://pic.netbian.com"


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
                self.items.append(
                    {
                        "id": match.group(1),
                        "href": self._href,
                        "src": self._src,
                        "alt": self._alt,
                        "title": title,
                    }
                )
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


def parse_list(html: str, query: str) -> list[AssetItem]:
    parser = _ListParser()
    parser.feed(html)
    normalized_query = query.casefold()
    result: list[AssetItem] = []
    for raw in parser.items:
        haystack = f"{raw['title']} {raw['alt']}".casefold()
        if normalized_query and normalized_query not in haystack:
            continue
        result.append(
            AssetItem(
                provider="netbian",
                id=raw["id"],
                preview_url=urljoin(_ROOT, raw["src"]),
                source_url=urljoin(_ROOT, raw["href"]),
                title=raw["title"],
                metadata={"detail_path": raw["href"]},
            )
        )
    return result


def parse_detail(html: str, item: AssetItem) -> AssetItem:
    parser = _DetailParser()
    parser.feed(html)
    if not parser.original:
        raise SpiderError(
            "netbian_invalid_response", "彼岸图网详情缺少原图地址", status=502
        )
    resolution = re.fullmatch(r"(\d+)x(\d+)", parser.resolution)
    metadata = dict(item.metadata)
    metadata.update(
        {
            "original_url": urljoin(_ROOT, parser.original),
            "category": parser.category,
            "resolution": parser.resolution,
        }
    )
    return replace(
        item,
        title=parser.title or item.title,
        preview_url=urljoin(_ROOT, parser.preview)
        if parser.preview
        else item.preview_url,
        width=int(resolution.group(1)) if resolution else item.width,
        height=int(resolution.group(2)) if resolution else item.height,
        metadata=metadata,
    )
