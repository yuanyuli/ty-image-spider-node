"""WallpapersCraft 壁纸来源。"""

from .client import WallpapersCraftClient, WallpapersCraftPage
from .provider import IMAGE_POLICY, WallpapersCraftProvider

__all__ = [
    "IMAGE_POLICY",
    "WallpapersCraftClient",
    "WallpapersCraftPage",
    "WallpapersCraftProvider",
]
