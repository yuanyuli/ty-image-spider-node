"""编辑精选与设计平台来源。"""

from .arena import ArenaProvider
from .behance import BehanceProvider
from .provider import EditorialProvider
from .sources import (
    APERTURE,
    COLOSSAL,
    DESIGN_MILK,
    FEATURE_SHOOT,
    MY_MODERN_MET,
    PRINT_MAGAZINE,
    EditorialSource,
)

__all__ = [
    "APERTURE",
    "COLOSSAL",
    "DESIGN_MILK",
    "FEATURE_SHOOT",
    "MY_MODERN_MET",
    "PRINT_MAGAZINE",
    "ArenaProvider",
    "BehanceProvider",
    "EditorialProvider",
    "EditorialSource",
]
