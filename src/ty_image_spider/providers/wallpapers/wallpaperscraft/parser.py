"""WallpapersCraft HTML 的纯解析函数。"""

import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

from ....domain import AssetItem, SpiderError
from ....infrastructure.security import require_https_host

_ROOT = "https://wallpaperscraft.com"
_SAFE_PATH = re.compile(r"^/download/[a-z0-9_-]+_([0-9]+)/([0-9]+x[0-9]+)$")


class _ListParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.items: list[dict[str, str]] = []
        self._path = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "a" and "wallpapers__link" in (values.get("class") or "").split():
            self._path = values.get("href") or ""
        elif (
            tag == "img"
            and self._path
            and "wallpapers__image" in (values.get("class") or "").split()
        ):
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


def parse_list(html: str) -> list[AssetItem]:
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


def parse_original(html: str, item: AssetItem) -> str:
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
    require_https_host(original, lambda host: host == "images.wallpaperscraft.com")
    return original
