"""来源无关的网络、路径和凭据安全工具。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable
from urllib.parse import ParseResult, urlparse

from .models import SpiderError


_SECRET_PARTS = ("key", "token", "secret", "cookie", "authorization")


def require_https_host(url: str, allowed: Callable[[str], bool]) -> ParseResult:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not host or not allowed(host):
        raise SpiderError("unsafe_url", "图片地址不属于当前素材源")
    return parsed


def resolve_inside(root: Path, relative: Path) -> Path:
    root_path = Path(root).resolve()
    relative_path = Path(relative)
    if relative_path.is_absolute():
        raise SpiderError("unsafe_path", "目标路径不在允许的输出目录内")
    candidate = (root_path / relative_path).resolve()
    try:
        candidate.relative_to(root_path)
    except ValueError as exc:
        raise SpiderError("unsafe_path", "目标路径不在允许的输出目录内") from exc
    return candidate


def read_limited(response: Any, max_bytes: int) -> bytes:
    raw_length = getattr(response, "headers", {}).get("Content-Length")
    if raw_length:
        try:
            if int(raw_length) > max_bytes:
                raise SpiderError("response_too_large", "远程文件超过大小限制")
        except ValueError:
            pass
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = response.read(min(1024 * 1024, max_bytes - total + 1))
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise SpiderError("response_too_large", "远程文件超过大小限制")
        chunks.append(chunk)
    return b"".join(chunks)


def redact_secrets(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[已隐藏]"
            if any(part in str(key).lower() for part in _SECRET_PARTS)
            else redact_secrets(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact_secrets(item) for item in value]
    return value
