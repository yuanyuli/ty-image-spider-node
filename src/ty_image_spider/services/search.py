"""搜索用例。"""

from __future__ import annotations

from typing import Mapping

from ..models import SearchPage, SearchRequest, SpiderError
from ..providers.registry import ProviderRegistry


class SearchService:
    def __init__(self, providers: ProviderRegistry) -> None:
        self._providers = providers

    def execute(self, payload: Mapping[str, object]) -> SearchPage:
        provider_id = payload.get("provider")
        if not isinstance(provider_id, str) or not provider_id:
            raise SpiderError("invalid_provider", "请求缺少有效的素材源")
        query = payload.get("query", "")
        if not isinstance(query, str):
            raise SpiderError("invalid_query", "搜索词必须是字符串")
        raw_filters = payload.get("filters", {})
        if not isinstance(raw_filters, Mapping):
            raise SpiderError("invalid_filters", "筛选条件必须是对象")
        filters = {str(key): value for key, value in raw_filters.items()}
        cursor = payload.get("cursor")
        if cursor is not None and not isinstance(cursor, str):
            raise SpiderError("invalid_cursor", "分页游标必须是字符串")
        refresh = payload.get("refresh", False)
        if not isinstance(refresh, bool):
            raise SpiderError("invalid_refresh", "刷新标记必须是布尔值")
        request = SearchRequest(
            provider_id,
            query,
            filters,
            cursor,
            refresh,
        )
        return self._providers.get(provider_id).search(request)
