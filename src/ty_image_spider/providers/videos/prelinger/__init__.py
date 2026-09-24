"""Prelinger Archives 视频来源公开入口。"""

from .client import PrelingerClient
from .normalizer import normalize_detail, normalize_search_item
from .provider import PrelingerProvider

__all__ = [
    "PrelingerClient",
    "PrelingerProvider",
    "normalize_detail",
    "normalize_search_item",
]
