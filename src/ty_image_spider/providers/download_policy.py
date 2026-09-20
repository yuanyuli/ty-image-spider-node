"""来源无关的下载规则，规则实例由各来源声明。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Protocol
from urllib.parse import quote, urlsplit, urlunsplit

from ..models import SpiderError
from ..security import require_https_host


class DownloadPolicy(Protocol):
    @property
    def provider_id(self) -> str: ...

    def validate_asset_id(self, item_id: str) -> None: ...
    def validate_url(self, url: str) -> None: ...
    def normalize_url(self, url: str) -> str: ...


@dataclass(frozen=True, slots=True)
class HostDownloadPolicy:
    provider_id: str
    host_rule: Callable[[str], bool]
    id_pattern: str = r"[0-9]+(?:-[0-9]+)?"
    safe_path_chars: str = "/%"

    def validate_asset_id(self, item_id: str) -> None:
        if not re.fullmatch(self.id_pattern, item_id):
            raise SpiderError("invalid_asset", "素材 ID 无效")

    def validate_url(self, url: str) -> None:
        try:
            parsed = require_https_host(url, self.host_rule)
            if (
                parsed.username is not None
                or parsed.password is not None
                or parsed.port not in (None, 443)
            ):
                raise ValueError("不接受凭据或非标准端口")
        except ValueError as exc:
            raise SpiderError("unsafe_url", "图片地址不属于当前素材源") from exc

    def normalize_url(self, url: str) -> str:
        self.validate_url(url)
        parts = urlsplit(url)
        return urlunsplit(
            (
                parts.scheme,
                parts.netloc,
                quote(parts.path, safe=self.safe_path_chars),
                quote(parts.query, safe="=&%+/:,?"),
                "",
            )
        )
