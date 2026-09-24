"""The Met API 客户端。"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Mapping

from ....domain import SpiderError
from ...shared import PublicJsonClient


class MetClient:
    def __init__(self, client: PublicJsonClient) -> None:
        self._client = client

    def search(self, query: str, department_id: int | None) -> list[int]:
        params: dict[str, object] = {
            "hasImages": "true",
            "isPublicDomain": "true",
            "q": query or "*",
        }
        if department_id is not None:
            params["departmentId"] = department_id
        data = self._client.get("search", params).data
        ids = data.get("objectIDs") if isinstance(data, Mapping) else None
        if ids is None:
            return []
        if not isinstance(ids, list):
            raise SpiderError(
                "met_invalid_response", "大都会博物馆搜索结果无效", status=502
            )
        return [
            value
            for value in ids
            if isinstance(value, int) and not isinstance(value, bool) and value > 0
        ]

    def object(self, object_id: int) -> Mapping[str, Any]:
        if object_id < 1:
            raise SpiderError("invalid_asset", "大都会博物馆素材 ID 无效")
        data = self._client.get(f"objects/{object_id}", {}).data
        if not isinstance(data, Mapping):
            raise SpiderError(
                "met_invalid_response", "大都会博物馆作品详情无效", status=502
            )
        return data

    def objects(self, object_ids: list[int]) -> list[Mapping[str, Any]]:
        if not object_ids:
            return []

        def fetch(object_id: int) -> Mapping[str, Any] | None:
            try:
                return self.object(object_id)
            except SpiderError:
                return None

        with ThreadPoolExecutor(max_workers=min(6, len(object_ids))) as executor:
            rows = executor.map(fetch, object_ids)
            return [row for row in rows if row is not None]
