"""素材详情用例。"""

from __future__ import annotations

from typing import Mapping

from ..models import AssetDetail, AssetItem
from ..providers.registry import ProviderRegistry


class DetailService:
    def __init__(self, providers: ProviderRegistry) -> None:
        self._providers = providers

    def execute(self, payload: Mapping[str, object]) -> AssetDetail:
        item = AssetItem.from_untrusted(payload.get("item"))
        return self._providers.get(item.provider).detail(item)
