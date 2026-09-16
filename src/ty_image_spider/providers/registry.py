"""Provider 的轻量注册表与工厂入口。"""

from __future__ import annotations

from ..models import ProviderDescriptor, SpiderError
from .base import AssetProvider


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, AssetProvider] = {}

    def register(self, provider: AssetProvider) -> None:
        if provider.id in self._providers:
            raise ValueError(f"Provider ID 重复：{provider.id}")
        self._providers[provider.id] = provider

    def get(self, provider_id: str) -> AssetProvider:
        try:
            return self._providers[provider_id]
        except KeyError as exc:
            raise SpiderError(
                "provider_not_found",
                f"未知素材源：{provider_id}",
                "请刷新素材源列表后重试",
                404,
            ) from exc

    def descriptors(self) -> tuple[ProviderDescriptor, ...]:
        return tuple(provider.descriptor() for provider in self._providers.values())

    def all(self) -> tuple[AssetProvider, ...]:
        return tuple(self._providers.values())
