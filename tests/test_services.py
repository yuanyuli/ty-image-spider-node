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
from ty_image_spider.services.detail import DetailService
from ty_image_spider.services.download import DownloadService
from ty_image_spider.services.search import SearchService
from ty_image_spider.services.status import StatusService


class RecordingProvider:
    def __init__(self, provider_id, *, bulk=False, status_error=None):
        self.id = provider_id
        self.bulk = bulk
        self.status_error = status_error
        self.search_calls = 0
        self.detail_calls = 0
        self.download_calls = 0

    def descriptor(self):
        return ProviderDescriptor(
            self.id,
            self.id.title(),
            capabilities=ProviderCapabilities(bulk_download=self.bulk),
        )

    def status(self):
        if self.status_error:
            raise self.status_error
        return ProviderStatus(True)

    def search(self, request):
        self.search_calls += 1
        return SearchPage((AssetItem(self.id, "1", title=request.query),))

    def detail(self, item):
        self.detail_calls += 1
        return AssetDetail(item, content="detail")

    def download(self, item, output_root):
        self.download_calls += 1
        return DownloadResult((f"{self.id}/{item.id}.png",), "已下载")


def registry_with(*providers):
    registry = ProviderRegistry()
    for provider in providers:
        registry.register(provider)
    return registry


def item_dict(provider="local", item_id="1"):
    return AssetItem(provider, item_id).to_dict()


def test_search_service_calls_only_selected_provider():
    civitai = RecordingProvider("civitai")
    local = RecordingProvider("local")
    service = SearchService(registry_with(civitai, local))

    result = service.execute({"provider": "local", "query": "cat", "filters": {}})

    assert result.items[0].provider == "local"
    assert result.items[0].title == "cat"
    assert local.search_calls == 1
    assert civitai.search_calls == 0


def test_search_service_rejects_invalid_payload_shape():
    service = SearchService(registry_with(RecordingProvider("local")))

    with pytest.raises(SpiderError, match="筛选条件"):
        service.execute({"provider": "local", "filters": []})
    with pytest.raises(SpiderError, match="素材源"):
        service.execute({"provider": ""})


def test_detail_service_uses_item_provider():
    local = RecordingProvider("local")

    result = DetailService(registry_with(local)).execute({"item": item_dict()})

    assert result.content == "detail"
    assert local.detail_calls == 1


def test_download_service_uses_configured_output_root(tmp_path):
    civitai = RecordingProvider("civitai")

    result = DownloadService(registry_with(civitai), tmp_path).execute(
        {"item": item_dict("civitai", "9")}
    )

    assert result.files == ("civitai/9.png",)
    assert result.output_root == str(tmp_path.resolve())
    assert civitai.download_calls == 1


def test_download_page_requires_provider_capability(tmp_path):
    xiaohongshu = RecordingProvider("xiaohongshu", bulk=False)
    service = DownloadService(registry_with(xiaohongshu), tmp_path)

    with pytest.raises(SpiderError, match="不支持整页下载"):
        service.download_page("xiaohongshu", [item_dict("xiaohongshu")])


def test_download_page_caps_items_and_rejects_mixed_provider(tmp_path):
    civitai = RecordingProvider("civitai", bulk=True)
    service = DownloadService(registry_with(civitai), tmp_path)

    result = service.download_page(
        "civitai", [item_dict("civitai", str(i)) for i in range(24)]
    )
    assert len(result.files) == 24

    with pytest.raises(SpiderError, match="最多下载 24"):
        service.download_page(
            "civitai", [item_dict("civitai", str(i)) for i in range(25)]
        )
    with pytest.raises(SpiderError, match="来源不一致"):
        service.download_page("civitai", [item_dict("local")])


def test_download_page_aggregates_results(tmp_path):
    civitai = RecordingProvider("civitai", bulk=True)

    result = DownloadService(registry_with(civitai), tmp_path).download_page(
        "civitai", [item_dict("civitai", "1"), item_dict("civitai", "2")]
    )

    assert result.files == ("civitai/1.png", "civitai/2.png")
    assert civitai.download_calls == 2


def test_status_service_lists_optional_failure_without_aborting():
    xhs = RecordingProvider(
        "xiaohongshu",
        status_error=SpiderError("opencli_missing", "未找到 OpenCLI", status=503),
    )
    local = RecordingProvider("local")

    result = StatusService(registry_with(xhs, local)).list()

    assert result[0]["status"]["available"] is False
    assert result[0]["status"]["code"] == "opencli_missing"
    assert result[1]["status"]["available"] is True
    assert StatusService(registry_with(local)).check("local").available is True
