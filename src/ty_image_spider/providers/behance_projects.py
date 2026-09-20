"""读取 Behance 公开项目连接及其真实分页游标。"""

from __future__ import annotations

import json
import uuid
from http.client import HTTPException
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..models import SpiderError
from ..network_retry import retry_call
from ..version import USER_AGENT
from ..security import read_limited, require_https_host


_FIELDS = """
nodes { ... on Project {
  id name url covers { allAvailable { url width } } owners { displayName }
} }
pageInfo { hasNextPage endCursor }
"""
_GALLERY = (
    "query($slug:String!,$after:String){gallery(slug:$slug){"
    "projects(first:24,after:$after){" + _FIELDS + "}}}"
)
_SEARCH = (
    "query($query:query,$after:String){"
    "search(query:$query,type:PROJECT,first:24,after:$after){" + _FIELDS + "}}"
)


class BehanceProjects:
    def __init__(self, open_url: Callable[..., Any] = urlopen) -> None:
        self._open_url = open_url

    def read(
        self, category: str, query: str, cursor: str | None
    ) -> tuple[list[Mapping[str, Any]], str | None]:
        if cursor is not None and (not isinstance(cursor, str) or len(cursor) > 512):
            raise SpiderError("invalid_cursor", "Behance 分页游标无效")
        variables = (
            {"after": cursor, "query": query}
            if query
            else {"after": cursor, "slug": category}
        )
        # 官网匿名客户端同样生成随机 bcp，与 X-BCP 配对；不读取用户登录凭据。
        csrf = str(uuid.uuid4())
        request = Request(
            "https://www.behance.net/v3/graphql",
            data=json.dumps(
                {"query": _SEARCH if query else _GALLERY, "variables": variables}
            ).encode(),
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 " + USER_AGENT,
                "Referer": "https://www.behance.net/",
                "X-Requested-With": "XMLHttpRequest",
                "X-BCP": csrf,
                "Cookie": f"bcp={csrf}",
            },
        )

        def fetch() -> Any:
            with self._open_url(request, timeout=30) as response:
                require_https_host(
                    response.geturl(), lambda host: host == "www.behance.net"
                )
                payload = json.loads(read_limited(response, 4 * 1024 * 1024))
            return payload

        try:
            payload = retry_call(fetch)
            if payload.get("errors"):
                raise ValueError("GraphQL response contains errors")
            data = payload["data"]
            connection = data["search"] if query else data["gallery"]["projects"]
            nodes, info = connection["nodes"], connection["pageInfo"]
            if not isinstance(nodes, list) or not isinstance(info, Mapping):
                raise ValueError("Invalid project connection")
            next_cursor = info.get("endCursor") if info.get("hasNextPage") else None
            if next_cursor is not None and (
                not isinstance(next_cursor, str) or not next_cursor
            ):
                raise ValueError("Invalid next cursor")
            if next_cursor and next_cursor == cursor:
                raise ValueError("Repeated cursor")
            return [node for node in nodes if isinstance(node, Mapping)], next_cursor
        except (HTTPError, URLError, TimeoutError, OSError, HTTPException) as exc:
            raise SpiderError(
                "behance_unavailable", "Behance 暂时无法访问，请稍后重试", status=502
            ) from exc
        except (KeyError, TypeError, AttributeError, ValueError) as exc:
            raise SpiderError(
                "behance_invalid_response", "Behance 分页数据无效", status=502
            ) from exc
