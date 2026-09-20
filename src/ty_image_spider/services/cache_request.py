"""不可变缓存请求：稳定指纹与任务私有的 JSON 快照。"""

from __future__ import annotations
import hashlib
import json
import math
from dataclasses import dataclass
from typing import Mapping
from ..models import SpiderError


def _validate_json(value: object, depth: int = 0) -> None:
    if depth > 32:
        raise ValueError("筛选层级过深")
    if isinstance(value, dict):
        for key, nested in value.items():
            if not isinstance(key, str):
                raise ValueError("键必须是字符串")
            _validate_json(nested, depth + 1)
    elif isinstance(value, list):
        for nested in value:
            _validate_json(nested, depth + 1)
    elif isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("数值必须有限")
    elif value is not None and not isinstance(value, (str, int, bool)):
        raise ValueError("筛选必须为 JSON 数据")


@dataclass(frozen=True, slots=True)
class CacheRequest:
    provider: str
    query: str
    filters_json: str

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> CacheRequest:
        provider = payload.get("provider")
        query = payload.get("query", "")
        filters = payload.get("filters", {})
        if (
            not isinstance(provider, str)
            or not provider
            or not isinstance(query, str)
            or not isinstance(filters, Mapping)
        ):
            raise SpiderError(
                "invalid_cache_request", "缓存请求缺少有效来源、搜索词或筛选条件"
            )
        if len(query) > 200:
            raise SpiderError("invalid_query", "搜索词过长")
        try:
            _validate_json(dict(filters))
            encoded = json.dumps(
                dict(filters),
                sort_keys=True,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            )
        except (ValueError, TypeError, RecursionError) as exc:
            raise SpiderError(
                "invalid_cache_request", "筛选条件必须为有效 JSON 对象"
            ) from exc
        return cls(provider, query.strip(), encoded)

    def to_payload(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "query": self.query,
            "filters": json.loads(self.filters_json),
        }

    def fingerprint(self) -> str:
        encoded = json.dumps(
            self.to_payload(), sort_keys=True, ensure_ascii=False, separators=(",", ":")
        )
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
