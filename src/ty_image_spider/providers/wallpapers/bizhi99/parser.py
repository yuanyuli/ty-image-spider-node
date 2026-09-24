"""壁纸网 HTML 的纯解析函数。"""

import re
from dataclasses import replace
from html.parser import HTMLParser
from urllib.parse import urljoin

from ....domain import AssetItem, SpiderError

_ROOT = "https://www.bizhi99.com"
_IMAGE_ROOT = "https://pic.bizhi66.com"


class _ListParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.items: list[dict[str, str]] = []
        self._link: dict[str, str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "a" and (values.get("href") or "").startswith("/bizhi/"):
            self._link = {
                "href": values.get("href") or "",
                "title": values.get("title") or "",
            }
        elif tag == "img" and self._link is not None:
            self._link["preview"] = (
                values.get("data-original") or values.get("src") or ""
            )
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


def parse_list(html: str, query: str) -> list[AssetItem]:
    parser = _ListParser()
    parser.feed(html)
    normalized_query = query.casefold()
    result: list[AssetItem] = []
    for raw in parser.items:
        title = raw.get("title") or raw.get("alt") or ""
        if normalized_query and normalized_query not in title.casefold():
            continue
        result.append(
            AssetItem(
                provider="bizhi99",
                id=raw["id"],
                preview_url=raw["preview"],
                source_url=urljoin(_ROOT, raw["href"]),
                title=title,
                metadata={"detail_path": raw["href"]},
            )
        )
    return result


def parse_detail(html: str, item: AssetItem) -> AssetItem:
    parser = _DetailParser()
    parser.feed(html)
    if not parser.original:
        raise SpiderError(
            "bizhi99_invalid_response", "壁纸网详情缺少原图地址", status=502
        )
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
