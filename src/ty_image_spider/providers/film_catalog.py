"""中文精选片名与 FilmGrab 搜索词映射，无外部翻译依赖。"""

from __future__ import annotations

import re

from ..models import FilterOption, SpiderError


FILMS = (
    ("银翼杀手", "Blade Runner", "霓虹与科幻", ("銀翼殺手",)),
    ("银翼杀手2049", "Blade Runner 2049", "霓虹与科幻", ("銀翼殺手2049",)),
    ("花样年华", "In the Mood for Love", "东方色彩", ("花樣年華",)),
    ("重庆森林", "Chungking Express", "都市夜色", ("重慶森林",)),
    ("堕落天使", "Fallen Angels", "都市夜色", ("墮落天使",)),
    ("布达佩斯大饭店", "The Grand Budapest Hotel", "对称与配色", ("布达佩斯大酒店",)),
    ("月升王国", "Moonrise Kingdom", "复古童话", ("月亮升起之王国",)),
    ("天使爱美丽", "Amelie", "法式色彩", ("天使艾米莉",)),
    ("爱乐之城", "La La Land", "歌舞与色彩", ("樂來越愛你",)),
    ("她", "Her", "柔和未来", ()),
    ("沙丘", "Dune (2021)", "2021 · 沙漠与尺度", ("沙丘2021",)),
    ("沙丘2", "Dune: Part 2", "沙漠与尺度", ("沙丘第二部", "Dune: Part Two")),
    ("星际穿越", "Interstellar", "宇宙与自然", ("星際效應",)),
    ("盗梦空间", "Inception", "空间与建筑", ("全面启动",)),
    ("2001太空漫游", "2001: A Space Odyssey", "经典科幻", ("太空漫游",)),
    ("巴黎德州", "Paris, Texas", "公路与孤独", ("德州巴黎",)),
    ("潜行者", "Stalker", "废墟与自然", ()),
    ("生命之树", "The Tree of Life", "自然光", ()),
    ("荒野猎人", "The Revenant", "自然光", ("神鬼猎人",)),
    (
        "疯狂的麦克斯狂暴之路",
        "Mad Max: Fury Road",
        "荒漠与动作",
        ("疯狂的麦克斯4", "狂暴之路"),
    ),
    ("英雄", "Hero", "东方色彩", ()),
    ("卧虎藏龙", "Crouching Tiger, Hidden Dragon", "山水与武侠", ("臥虎藏龍",)),
    ("刺客聂隐娘", "The Assassin", "东方构图", ("聂隐娘",)),
    ("千与千寻", "Spirited Away", "动画与幻想", ("神隐少女", "千與千尋")),
)

# 2026-09-19 由 FilmGrab 公开 WordPress API 核实，避免全文关键词匹配到其他电影。
_POST_IDS = {
    "Blade Runner": 826,
    "Blade Runner 2049": 136782,
    "In the Mood for Love": 18034,
    "Chungking Express": 59696,
    "Fallen Angels": 35347,
    "The Grand Budapest Hotel": 44361,
    "Moonrise Kingdom": 15864,
    "Amelie": 13735,
    "La La Land": 138092,
    "Her": 37847,
    "Dune (2021)": 151243,
    "Dune: Part 2": 157643,
    "Interstellar": 76413,
    "Inception": 11381,
    "2001: A Space Odyssey": 1309,
    "Paris, Texas": 501,
    "Stalker": 9760,
    "The Tree of Life": 12603,
    "The Revenant": 116073,
    "Mad Max: Fury Road": 91539,
    "Hero": 18031,
    "Crouching Tiger, Hidden Dragon": 112733,
    "The Assassin": 130156,
    "Spirited Away": 145164,
}


def film_post_id(query: str) -> int | None:
    return _POST_IDS.get(query)


def display_film_title(english: str) -> str:
    for chinese, title, _, _ in FILMS:
        if _normalize(english) == _normalize(title):
            return f"{chinese} / {english}"
    return english


def _normalize(value: str) -> str:
    return re.sub(r"[\s《》:：·\-]", "", value).casefold()


def resolve_film_query(query: str) -> str:
    query = query.strip()
    normalized = _normalize(query)
    for chinese, english, _, aliases in FILMS:
        if normalized in {_normalize(name) for name in (chinese, english, *aliases)}:
            return english
    if re.search(r"[\u3400-\u9fff]", query):
        raise SpiderError(
            "film_title_unknown",
            "暂未收录这个中文片名，请从中文片单选择，或清空关键词浏览全部电影",
        )
    return query


def film_presets() -> tuple[FilterOption, ...]:
    return tuple(
        FilterOption(chinese, f"{chinese} · {style}") for chinese, _, style, _ in FILMS
    )
