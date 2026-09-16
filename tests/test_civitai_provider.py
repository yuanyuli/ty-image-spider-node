import json
from pathlib import Path

from ty_image_spider.cache import JsonCache
from ty_image_spider.models import DownloadResult, SearchRequest, SpiderError
from ty_image_spider.providers.civitai import CivitaiProvider
from ty_image_spider.providers.civitai_client import CivitaiPage


FIXTURE = json.loads((Path(__file__).parent / "fixtures/civitai_images.json").read_text())


class FakeClient:
    def __init__(self, error=None):
        self.error = error
        self.calls = []

    def search(self, site, params):
        self.calls.append((site, params))
        if self.error:
            raise self.error
        return CivitaiPage(tuple(FIXTURE["items"]), "cursor-2")

    def page_metadata(self, site, image_id):
        return {}


class FakeDownloader:
    def download(self, url, item_id, output_root):
        return DownloadResult((f"ty-image-spider/civitai/{item_id}.png",), "已下载")


def make_provider(tmp_path, client=None):
    return CivitaiProvider(client or FakeClient(), JsonCache(tmp_path), FakeDownloader())


def test_civitai_provider_maps_filters_and_normalizes_prompt(tmp_path):
    client = FakeClient()
    provider = make_provider(tmp_path, client)
    page = provider.search(
        SearchRequest(
            "civitai",
            "portrait",
            {
                "site": "civitai.com",
                "period": "Week",
                "sort": "Most Reactions",
                "sfw": True,
                "tag": "Portrait",
                "only_with_prompt": True,
                "count": 6,
            },
        )
    )

    assert [item.id for item in page.items] == ["101"]
    assert page.items[0].prompt == "cinematic cat"
    assert page.items[0].negative_prompt == "blur"
    assert page.items[0].metadata["models"] == [{"type": "model", "name": "Base XL"}]
    assert page.items[0].metadata["loras"] == [{"type": "lora", "name": "Detail LoRA"}]
    assert page.next_cursor == "cursor-2"
    site, params = client.calls[0]
    assert site == "civitai.com"
    assert params["period"] == "Week"
    assert params["sort"] == "Most Reactions"
    assert params["tag"] == 1441
    assert params["nsfw"] == "None"


def test_civitai_provider_does_not_treat_workflow_as_prompt(tmp_path):
    page = make_provider(tmp_path).search(
        SearchRequest("civitai", filters={"only_with_prompt": False})
    )

    workflow = page.items[1]
    assert workflow.has_prompt is False
    assert workflow.prompt is None
    assert workflow.metadata["workflow"] == {"nodes": []}


def test_civitai_timeout_returns_marked_stale_cache(tmp_path):
    provider = make_provider(tmp_path)
    request = SearchRequest("civitai", "cat", {"site": "civitai.com"})
    first = provider.search(request)
    provider = make_provider(
        tmp_path,
        FakeClient(SpiderError("civitai_timeout", "超时", status=504)),
    )

    stale = provider.search(request)

    assert first.items
    assert stale.stale is True
    assert stale.items[0].id == first.items[0].id


def test_civitai_descriptor_and_download_capabilities(tmp_path):
    provider = make_provider(tmp_path)
    descriptor = provider.descriptor()
    item = provider.search(SearchRequest("civitai")).items[0]

    assert descriptor.capabilities.bulk_download is True
    assert {field.name for field in descriptor.filters} >= {"site", "period", "sort", "sfw", "tag"}
    assert provider.download(item, tmp_path).files == ("ty-image-spider/civitai/101.png",)

