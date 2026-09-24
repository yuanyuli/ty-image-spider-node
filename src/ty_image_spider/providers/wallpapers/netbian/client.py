"""彼岸图网受限 HTML 客户端。"""

import re
from dataclasses import dataclass
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from ....domain import SpiderError
from ....infrastructure.security import read_limited, require_https_host
from ....version import USER_AGENT

_ROOT = "https://pic.netbian.com"
_SAFE_ID = re.compile(r"^[0-9]+$")


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
            request = Request(
                url, headers={"Accept": "text/html", "User-Agent": USER_AGENT}
            )
            with self._open_url(request, timeout=self._timeout_seconds) as response:
                require_https_host(
                    response.geturl(), lambda host: host == "pic.netbian.com"
                )
                return read_limited(response, 8 * 1024 * 1024).decode(
                    "utf-8", errors="replace"
                )
        except SpiderError:
            raise
        except HTTPError as exc:
            raise SpiderError(
                "netbian_http_error", f"彼岸图网请求失败（{exc.code}）", status=502
            ) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise SpiderError(
                "netbian_unavailable", "无法连接彼岸图网", status=502
            ) from exc


def _page_url(path: str, page: int) -> str:
    if page == 1:
        return urljoin(_ROOT, path)
    return urljoin(_ROOT, path.rstrip("/") + f"/index_{page}.html")


def _last_page(html: str) -> int:
    pages = [int(value) for value in re.findall(r"index_(\d+)\.html", html)]
    return max(pages, default=1)
