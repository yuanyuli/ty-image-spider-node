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
