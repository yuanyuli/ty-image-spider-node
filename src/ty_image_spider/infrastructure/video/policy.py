"""视频下载的来源主机、素材 ID 和容量策略。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Pattern
from urllib.parse import urlsplit

from ...domain import SpiderError


@dataclass(frozen=True, slots=True)
class VideoDownloadPolicy:
    provider_id: str
    host_rule: Callable[[str], bool]
    id_pattern: str | Pattern[str]
    max_bytes: int = 2 * 1024**3
    _compiled_id: Pattern[str] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        compiled = (
            re.compile(self.id_pattern)
            if isinstance(self.id_pattern, str)
            else self.id_pattern
        )
        object.__setattr__(self, "_compiled_id", compiled)
        if not self.provider_id or self.max_bytes <= 0:
            raise ValueError("视频下载策略无效")

    def require_item_id(self, item_id: str) -> None:
        if not self._compiled_id.fullmatch(item_id):
            raise SpiderError("invalid_asset", "视频素材 ID 无效")

    def require_url(self, url: str) -> None:
        try:
            parsed = urlsplit(url)
            port = parsed.port
        except ValueError as exc:
            raise SpiderError("unsafe_url", "视频地址无效") from exc
        host = (parsed.hostname or "").lower()
        if (
            parsed.scheme != "https"
            or not host
            or parsed.username is not None
            or parsed.password is not None
            or port not in {None, 443}
            or not self.host_rule(host)
        ):
            raise SpiderError("unsafe_url", "视频地址不在允许范围内")
