"""小红书搜索页的持久缓存编码与恢复。"""

import hashlib
from dataclasses import replace
from typing import Mapping
from urllib.parse import urlsplit, urlunsplit

from ....domain import AssetItem, SearchPage, SpiderError


def cache_key(
    query: str, sort: str, note_type: str, publish_time: str, count: int
) -> str:
    raw = "\0".join((query, sort, note_type, publish_time, str(count)))
    return "xiaohongshu:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def persistent_page(page: SearchPage) -> dict[str, object]:
    items = []
    for item in page.items:
        preview = without_query(item.preview_url) if item.preview_url else None
        items.append(replace(item, preview_url=preview, source_url=None).to_dict())
    return {"items": items}


def cached_page(value: object) -> SearchPage:
    if not isinstance(value, Mapping) or not isinstance(value.get("items"), list):
        raise SpiderError("cache_invalid", "小红书缓存数据无效", status=502)
    items = tuple(AssetItem.from_untrusted(item) for item in value["items"])
    return SearchPage(
        items, stale=True, message="正在显示短期缓存结果，请重新搜索后查看详情"
    )


def without_query(url: str) -> str:
    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
