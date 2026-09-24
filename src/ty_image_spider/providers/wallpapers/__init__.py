"""壁纸来源。"""

from .bizhi99 import Bizhi99Client, Bizhi99Provider
from .netbian import NetbianClient, NetbianProvider
from .wallhaven import WallhavenClient, WallhavenDownloader, WallhavenProvider
from .wallpaperscraft import WallpapersCraftClient, WallpapersCraftProvider

__all__ = [
    "Bizhi99Client",
    "Bizhi99Provider",
    "NetbianClient",
    "NetbianProvider",
    "WallhavenClient",
    "WallhavenDownloader",
    "WallhavenProvider",
    "WallpapersCraftClient",
    "WallpapersCraftProvider",
]
