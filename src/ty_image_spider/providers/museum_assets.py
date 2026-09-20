"""馆藏素材的公共校验与详情组装；分类、检索和字段映射由各 Provider 负责。"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any, Mapping

from ..models import (
    AssetDetail,
    AssetItem,
    FilterField,
    FilterOption,
    SearchRequest,
    SpiderError,
)
from .download_policy import DownloadPolicy


def page_number(request: SearchRequest) -> int:
    raw = request.cursor or "1"
    if not re.fullmatch(r"[1-9][0-9]{0,4}", raw) or int(raw) > 10000:
        raise SpiderError("invalid_cursor", "馆藏页码无效")
    return int(raw)


def category(
    request: SearchRequest, choices: Mapping[str, object], default: str
) -> str:
    value = request.filters.get("category", default)
    if not isinstance(value, str) or value not in choices:
        raise SpiderError("invalid_category", "馆藏分类无效，请重新选择")
    return value


def category_field(
    choices: Mapping[str, tuple[str, object]], default: str
) -> FilterField:
    return FilterField(
        "category",
        "馆藏分类",
        "select",
        default,
        tuple(FilterOption(key, entry[0]) for key, entry in choices.items()),
    )


def records(data: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    rows = data.get(key)
    if not isinstance(rows, list):
        raise SpiderError("museum_invalid_response", "馆藏列表数据无效", status=502)
    return [row for row in rows if isinstance(row, Mapping)]


def object_data(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def integer(value: object) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return max(0, value)
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return 0


def plain_text(value: object) -> str:
    if not isinstance(value, str):
        return ""

    class Text(HTMLParser):
        def __init__(self) -> None:
            super().__init__(convert_charrefs=True)
            self.parts: list[str] = []

        def handle_data(self, data: str) -> None:
            self.parts.append(data)

    parser = Text()
    parser.feed(value[:20000])
    return " ".join(" ".join(parser.parts).split())


def image_url(value: object, source: DownloadPolicy) -> str:
    if not isinstance(value, str) or not value:
        return ""
    try:
        source.validate_url(value)
    except SpiderError:
        return ""
    return value


def require_item(item: AssetItem, source: DownloadPolicy) -> None:
    if item.provider != source.provider_id:
        raise SpiderError("invalid_asset", "素材来源与馆藏不一致")
    source.validate_asset_id(item.id)


def collection_detail(item: AssetItem, source: DownloadPolicy) -> AssetDetail:
    require_item(item, source)
    original = image_url(item.metadata.get("original_url"), source)
    if not original:
        raise SpiderError("invalid_asset", "馆藏图片地址无效")
    return AssetDetail(
        item, (original,), content=plain_text(item.metadata.get("description"))
    )
