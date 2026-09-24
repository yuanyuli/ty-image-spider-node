"""壁纸网受限 HTML 客户端。"""

import re
from dataclasses import dataclass
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from ....domain import SpiderError
from ....infrastructure.security import read_limited, require_https_host
from ....version import USER_AGENT

_ROOT = "https://www.bizhi99.com"
_SAFE_ID = re.compile(r"^[0-9]+$")


@dataclass(frozen=True, slots=True)
class Bizhi99ListPage:
    html: str
    current_page: int
    last_page: int


class Bizhi99Client:
    """只负责壁纸网页面请求。"""

    def __init__(
        self, open_url: Callable[..., Any] = urlopen, *, timeout_seconds: int = 30
    ) -> None:
        self._open_url = open_url
        self._timeout_seconds = timeout_seconds

    def list(self, path: str, page: int) -> Bizhi99ListPage:
        if page < 1:
            raise SpiderError("invalid_page", "分页必须是正整数")
        html = self._request(_page_url(path, page))
        page_prefix = re.escape(path.rstrip("/"))
        pages = [
            int(value) for value in re.findall(rf"{page_prefix}/(\d+)\.html", html)
        ]
        return Bizhi99ListPage(html, page, max([page, *pages]))

    def detail(self, item_id: str) -> str:
        if not _SAFE_ID.fullmatch(item_id):
            raise SpiderError("invalid_asset", "壁纸网素材 ID 无效")
        return self._request(f"{_ROOT}/bizhi/{item_id}.html")

    def _request(self, url: str) -> str:
        try:
            request = Request(
                url, headers={"Accept": "text/html", "User-Agent": USER_AGENT}
            )
            with self._open_url(request, timeout=self._timeout_seconds) as response:
                require_https_host(
                    response.geturl(),
                    lambda host: host in {"www.bizhi99.com", "bizhi99.com"},
                )
                return read_limited(response, 8 * 1024 * 1024).decode(
                    "utf-8", errors="replace"
                )
        except SpiderError:
            raise
        except HTTPError as exc:
            raise SpiderError(
                "bizhi99_http_error", f"壁纸网请求失败（{exc.code}）", status=502
            ) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise SpiderError(
                "bizhi99_unavailable", "无法连接壁纸网", status=502
            ) from exc


def _page_url(path: str, page: int) -> str:
    if page == 1:
        return urljoin(_ROOT, path)
    return urljoin(_ROOT, path.rstrip("/") + f"/{page}.html")
