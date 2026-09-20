"""素材详情用例。"""

from __future__ import annotations

from typing import Mapping

from ..models import AssetDetail, AssetItem
from ..asset_index import AssetIndex
from ..providers.registry import ProviderRegistry


class DetailService:
    def __init__(
        self, providers: ProviderRegistry, index: AssetIndex | None = None
    ) -> None:
        self._providers = providers
        self._index = index

    def execute(self, payload: Mapping[str, object]) -> AssetDetail:
        item = AssetItem.from_untrusted(payload.get("item"))
        if self._index is not None:
            cached = self._index.detail(item)
            if cached is not None:
                return cached
        return self._providers.get(item.provider).detail(item)
