"""Provider 协议、注册表和通用适配器。"""

from .base import AssetProvider
from .curated_client import BehanceClient, FilmGrabClient
from .curated_download import CuratedDownloader
from .download_policy import DownloadPolicy, HostDownloadPolicy
from .image_readers import ImageReaderRegistry
from .public_json_client import PublicJsonClient
from .registry import ProviderRegistry

__all__ = [
    "AssetProvider",
    "BehanceClient",
    "CuratedDownloader",
    "DownloadPolicy",
    "FilmGrabClient",
    "HostDownloadPolicy",
    "ImageReaderRegistry",
    "ProviderRegistry",
    "PublicJsonClient",
]
