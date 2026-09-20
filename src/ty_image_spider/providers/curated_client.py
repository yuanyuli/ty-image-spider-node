"""公开策展站点的受限读取客户端。"""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from http.client import HTTPException, IncompleteRead
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from ..models import SpiderError
from ..security import read_limited, require_https_host
from .behance_projects import BehanceProjects
from .film_catalog import film_post_id


class BehanceClient:
    def __init__(self, open_url: Callable[..., Any] = urlopen) -> None:
        self._open_url = open_url
        self._projects = BehanceProjects(open_url)

    def projects(
        self, category: str, query: str, cursor: str | None = None
    ) -> tuple[list[Mapping[str, Any]], str | None]:
        return self._projects.read(category, query, cursor)

    def images(self, item_id: str) -> tuple[str, ...]:
        if not item_id.isdigit():
            raise SpiderError("invalid_asset", "Behance 项目 ID 无效")
        markup = self._read(
            f"https://www.behance.net/gallery/{item_id}/project"
        ).decode("utf-8")
        return parse_project_images(markup, item_id)

    def _read(self, url: str) -> bytes:
        request = Request(
            url, headers={"User-Agent": "Mozilla/5.0", "Accept": "text/html"}
        )
        try:
            with self._open_url(request, timeout=30) as response:
                require_https_host(
                    response.geturl(), lambda host: host == "www.behance.net"
                )
                return read_limited(response, 12 * 1024 * 1024)
        except (HTTPError, URLError, TimeoutError, OSError, HTTPException) as exc:
            raise SpiderError(
                "behance_unavailable", "Behance 暂时无法访问", status=502
            ) from exc


class FilmGrabClient:
    def __init__(self, open_url: Callable[..., Any] = urlopen) -> None:
        self._open_url = open_url

    def posts(
        self, query: str, page: int, post_id: int | None = None
    ) -> tuple[list[Mapping[str, Any]], int]:
        params = {"per_page": 1, "page": page, "_fields": "id,link,title,content"}
        movie_id = post_id or film_post_id(query)
        if movie_id:
            params["include"] = movie_id
        elif query:
            params["search"] = query
        return self._request_posts(params)

    def catalogue(self, query: str) -> list[Mapping[str, Any]]:
        posts, _ = self._request_posts(
            {
                "search": query,
                "search_columns[]": "post_title",
                "per_page": 100,
                "_embed": "wp:term",
                "_fields": "id,title,link,_embedded,_links",
            }
        )
        return posts

    def _request_posts(
        self, params: Mapping[str, object]
    ) -> tuple[list[Mapping[str, Any]], int]:
        url = "https://film-grab.com/wp-json/wp/v2/posts?" + urlencode(params)
        request = Request(
            url,
            headers={"User-Agent": "TY-Image-Spider/2.0", "Accept": "application/json"},
        )
        for attempt in range(2):
            try:
                with self._open_url(request, timeout=30) as response:
                    require_https_host(
                        response.geturl(), lambda host: host == "film-grab.com"
                    )
                    last_page = int(response.headers.get("X-WP-TotalPages", "1"))
                    data = json.loads(read_limited(response, 4 * 1024 * 1024))
                    if not isinstance(data, list):
                        raise ValueError("posts is not a list")
                    return [
                        post for post in data if isinstance(post, Mapping)
                    ], last_page
            except (HTTPError, URLError, TimeoutError, OSError, HTTPException) as exc:
                if isinstance(exc, IncompleteRead) and attempt == 0:
                    continue
                raise SpiderError(
                    "filmgrab_unavailable", "FilmGrab 暂时无法访问", status=502
                ) from exc
            except (ValueError, json.JSONDecodeError) as exc:
                raise SpiderError(
                    "filmgrab_invalid_response", "FilmGrab 返回数据无效", status=502
                ) from exc
        raise AssertionError("unreachable")


def parse_project_images(markup: str, item_id: str) -> tuple[str, ...]:
    class ProjectImages(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self.images: list[str] = []

        def handle_starttag(
            self, tag: str, attrs: list[tuple[str, str | None]]
        ) -> None:
            if tag != "img":
                return
            url = dict(attrs).get("src") or ""
            parsed = urlparse(url)
            name = parsed.path.rsplit("/", 1)[-1]
            if (
                parsed.scheme == "https"
                and (parsed.hostname or "").endswith(".behance.net")
                and "/project_modules/" in parsed.path
                and re.match(r"^[a-f0-9]{6}" + re.escape(item_id) + r"\.", name)
                and url not in self.images
            ):
                self.images.append(url)

    parser = ProjectImages()
    parser.feed(markup)
    return tuple(parser.images[:100])
