"""素材来源策略。"""

from .base import AssetProvider
from .registry import ProviderRegistry

__all__ = ["AssetProvider", "ProviderRegistry"]

