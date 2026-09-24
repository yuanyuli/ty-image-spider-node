"""TY Image Spider 的稳定领域模型。"""

from .assets import AssetDetail, AssetItem
from .errors import SpiderError
from .json_types import JsonValue
from .operations import DownloadResult, SearchPage, SearchRequest
from .providers import (
    FilterField,
    FilterOption,
    ProviderCapabilities,
    ProviderDescriptor,
    ProviderPresentation,
    ProviderStatus,
)

__all__ = [
    "AssetDetail",
    "AssetItem",
    "DownloadResult",
    "FilterField",
    "FilterOption",
    "JsonValue",
    "ProviderCapabilities",
    "ProviderDescriptor",
    "ProviderPresentation",
    "ProviderStatus",
    "SearchPage",
    "SearchRequest",
    "SpiderError",
]
