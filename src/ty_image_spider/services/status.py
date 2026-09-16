"""素材源描述与可用性用例。"""

from __future__ import annotations

from ..models import ProviderStatus, SpiderError
from ..providers.registry import ProviderRegistry


class StatusService:
    def __init__(self, providers: ProviderRegistry) -> None:
        self._providers = providers

    def list(self) -> tuple[dict[str, object], ...]:
        result: list[dict[str, object]] = []
        for provider in self._providers.all():
            try:
                status = provider.status()
            except SpiderError as exc:
                status = ProviderStatus(False, exc.code, exc.message, exc.action)
            result.append(
                {
                    "provider": provider.descriptor().to_dict(),
                    "status": status.to_dict(),
                }
            )
        return tuple(result)

    def check(self, provider_id: str) -> ProviderStatus:
        provider = self._providers.get(provider_id)
        try:
            return provider.status()
        except SpiderError as exc:
            return ProviderStatus(False, exc.code, exc.message, exc.action)
