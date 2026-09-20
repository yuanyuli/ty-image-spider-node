"""专题来源配置：各网站真实分类/标签映射，不承担网络或图集解析。"""

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class EditorialSource:
    id: str
    label: str
    api_root: str
    categories: Mapping[str, tuple[str, str, int]]
    default: str
    page_size: int = 24
    prefer_original_preview: bool = False


COLOSSAL = EditorialSource(
    "colossal",
    "Colossal",
    "https://www.thisiscolossal.com/wp-json/wp/v2/",
    {
        "photography": ("当代摄影", "categories", 496),
        "design": ("设计", "categories", 494),
        "illustration": ("插画", "categories", 1327),
        "art": ("当代艺术", "categories", 493),
        "craft": ("手工与材质", "categories", 1312),
        "books": ("艺术书籍", "categories", 3059),
        "all": ("全部专题", "", 0),
    },
    "photography",
)

DESIGN_MILK = EditorialSource(
    "designmilk",
    "Design Milk",
    "https://design-milk.com/wp-json/wp/v2/",
    {
        "graphic": ("平面设计", "tags", 206),
        "photography": ("摄影", "tags", 93),
        "art": ("视觉艺术", "categories", 7),
        "fashion": ("时尚与配饰", "categories", 9),
        "interior": ("空间设计", "categories", 195),
        "furniture": ("家具与产品", "categories", 3),
        "all": ("全部专题", "", 0),
    },
    "graphic",
)

FEATURE_SHOOT = EditorialSource(
    "featureshoot",
    "Feature Shoot",
    "https://www.featureshoot.com/wp-json/wp/v2/",
    {
        "fine_art": ("艺术摄影", "categories", 11889),
        "documentary": ("纪实摄影", "categories", 11890),
        "portraits": ("人像", "categories", 11888),
        "nature": ("自然", "categories", 11897),
        "landscape": ("风景", "categories", 11891),
        "street": ("街头", "categories", 11892),
        "still_life": ("静物", "categories", 11894),
        "all": ("全部专题", "", 0),
    },
    "fine_art",
    prefer_original_preview=True,
)

MY_MODERN_MET = EditorialSource(
    "mymodernmet",
    "My Modern Met",
    "https://mymodernmet.com/wp-json/wp/v2/",
    {
        "art": ("当代艺术", "categories", 3),
        "photography": ("摄影", "categories", 4),
        "design": ("设计", "categories", 2),
        "architecture": ("建筑", "categories", 62577),
        "sculpture": ("雕塑", "categories", 109465),
        "installation": ("装置艺术", "categories", 109469),
        "painting": ("绘画", "categories", 109467),
        "all": ("全部专题", "", 0),
    },
    "art",
    12,
)
