"""WallpapersCraft 受限 HTML 客户端。"""

import re
from dataclasses import dataclass
from gzip import GzipFile
from io import BytesIO
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

from ....domain import SpiderError
from ....infrastructure.security import read_limited, require_https_host
from ....version import USER_AGENT

_ROOT = "https://wallpaperscraft.com"
_MAX_HTML_BYTES = 8 * 1024 * 1024
_SAFE_PATH = re.compile(r"^/download/[a-z0-9_-]+_([0-9]+)/([0-9]+x[0-9]+)$")
_CATEGORIES = {
    "nature",
    "city",
    "abstract",
    "space",
    "anime",
    "animals",
    "cars",
    "minimalism",
}
_RESOLUTIONS = ("1920x1080", "2560x1440", "3840x2160", "3440x1440")


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
        pages = [int(value) for value in re.findall(r"(?:page|[?&]page=)(\d+)", html)]
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
                    lambda host: (
                        host in {"wallpaperscraft.com", "www.wallpaperscraft.com"}
                    ),
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
