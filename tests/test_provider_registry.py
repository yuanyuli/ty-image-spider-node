import pytest

from ty_image_spider.models import (
    AssetDetail,
    AssetItem,
    DownloadResult,
    ProviderCapabilities,
    ProviderDescriptor,
    ProviderStatus,
    SearchPage,
    SpiderError,
)
from ty_image_spider.providers.registry import ProviderRegistry


class FakeProvider:
    def __init__(self, provider_id: str):
        self.id = provider_id

    def descriptor(self):
        return ProviderDescriptor(
            id=self.id,
            label=self.id,
            capabilities=ProviderCapabilities(),
        )

    def status(self):
        return ProviderStatus(available=True)

    def search(self, request):
        return SearchPage()

    def detail(self, item: AssetItem):
        return AssetDetail(item=item)

    def download(self, item, output_root):
        return DownloadResult()


def test_registry_rejects_duplicate_provider_ids():
    registry = ProviderRegistry()
    registry.register(FakeProvider("civitai"))

    with pytest.raises(ValueError, match="重复"):
        registry.register(FakeProvider("civitai"))


def test_registry_returns_provider_and_ordered_descriptors():
    registry = ProviderRegistry()
    local = FakeProvider("local")
    civitai = FakeProvider("civitai")
    registry.register(local)
    registry.register(civitai)

    assert registry.get("local") is local
    assert [descriptor.id for descriptor in registry.descriptors()] == ["local", "civitai"]


def test_registry_uses_domain_error_for_unknown_provider():
    with pytest.raises(SpiderError) as caught:
        ProviderRegistry().get("unknown")

    assert caught.value.code == "provider_not_found"

