import json
from pathlib import Path

from ty_image_spider.cache import JsonCache
from ty_image_spider.models import (
    AssetDetail,
    AssetItem,
    DownloadResult,
    SearchRequest,
    SpiderError,
)
from ty_image_spider.asset_index import AssetIndex
from ty_image_spider.providers.civitai import CivitaiProvider
from ty_image_spider.providers.civitai_client import CivitaiPage


FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures/civitai_images.json").read_text()
)


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


def test_cached_metadata_skips_remote_prompt_lookup_and_satisfies_filter(tmp_path):
    class Client(DetailPromptClient):
        def page_metadata(self, site, image_id):
            raise AssertionError("缓存命中不应再次请求详情")

    index = AssetIndex(tmp_path)
    saved = AssetItem(
        "civitai",
        "301",
        prompt="cached prompt",
        has_prompt=True,
        metadata={"site": "civitai.com"},
    )
    index.store(AssetDetail(saved), b"image", ".png")
    provider = CivitaiProvider(
        Client(),
        JsonCache(tmp_path / "query"),
        None,
        cached_asset=index.cached_original,
    )
    page = provider.search(SearchRequest("civitai", filters={"only_with_prompt": True}))
    assert len(page.items) == 1
    assert page.items[0].prompt == "cached prompt"


class PromptPagingClient(FakeClient):
    def search(self, site, params):
        self.calls.append((site, dict(params)))
        cursor = params.get("cursor")
        if cursor is None:
            return CivitaiPage(
                ({"id": 201, "url": "https://image.civitai.com/201.png", "meta": {}},),
                "page-2",
            )
        return CivitaiPage(
            (
                {
                    "id": 202,
                    "url": "https://image.civitai.com/202.png",
                    "meta": {"prompt": "second page prompt"},
                },
            ),
            None,
        )

    def page_metadata(self, site, image_id):
        return {"prompt": "first page prompt"} if image_id == "201" else {}


class DetailPromptClient(FakeClient):
    def search(self, site, params):
        self.calls.append((site, dict(params)))
        return CivitaiPage(
            ({"id": 301, "url": "https://image.civitai.com/301.png", "meta": {}},),
            None,
        )

    def page_metadata(self, site, image_id):
        return {"prompt": "prompt from detail page"} if image_id == "301" else {}


class HiddenPromptClient(DetailPromptClient):
    detail_calls = 0

    def page_metadata(self, site, image_id):
        self.detail_calls += 1
        return {"hasPositivePrompt": False, "prompt": "private prompt"}


class ManyMissingPromptClient(FakeClient):
    def __init__(self):
        super().__init__()
        self.detail_calls = 0

    def search(self, site, params):
        return CivitaiPage(
            tuple(
                {
                    "id": 400 + index,
                    "url": f"https://image.civitai.com/{400 + index}.png",
                    "meta": {},
                }
                for index in range(30)
            ),
            None,
        )

    def page_metadata(self, site, image_id):
        self.detail_calls += 1
        return {}


class FakeDownloader:
    def download(self, url, item_id, output_root):
        return DownloadResult((f"ty-image-spider/civitai/{item_id}.png",), "已下载")


def make_provider(tmp_path, client=None):
    return CivitaiProvider(
        client or FakeClient(), JsonCache(tmp_path), FakeDownloader()
    )


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
    assert params["tags"] == 1441
    assert params["nsfw"] == "false"


def test_only_with_prompt_enriches_missing_metadata_and_continues_pages(tmp_path):
    client = PromptPagingClient()
    page = make_provider(tmp_path, client).search(
        SearchRequest(
            "civitai", filters={"only_with_prompt": True, "count": 2, "sfw": False}
        )
    )

    assert [item.id for item in page.items] == ["201", "202"]
    assert [item.prompt for item in page.items] == [
        "first page prompt",
        "second page prompt",
    ]
    assert client.calls[0][1]["nsfw"] == "true"
    assert client.calls[1][1]["cursor"] == "page-2"


def test_civitai_provider_does_not_treat_workflow_as_prompt(tmp_path):
    page = make_provider(tmp_path).search(
        SearchRequest("civitai", filters={"only_with_prompt": False})
    )

    workflow = page.items[1]
    assert workflow.has_prompt is False
    assert workflow.prompt is None
    assert workflow.metadata["workflow"] == {"nodes": []}


def test_search_enriches_prompt_badge_when_list_metadata_is_missing(tmp_path):
    page = make_provider(tmp_path, DetailPromptClient()).search(
        SearchRequest("civitai", filters={"count": 1})
    )

    assert page.items[0].has_prompt is True
    assert page.items[0].prompt == "prompt from detail page"
    assert page.items[0].metadata["classification"] == "B"


def test_search_does_not_expose_prompt_marked_private_by_detail_page(tmp_path):
    page = make_provider(tmp_path, HiddenPromptClient()).search(
        SearchRequest("civitai", filters={"count": 1})
    )

    assert page.items[0].has_prompt is False
    assert page.items[0].prompt is None


def test_search_caps_prompt_enrichment_requests(tmp_path):
    client = ManyMissingPromptClient()
    make_provider(tmp_path, client).search(
        SearchRequest("civitai", filters={"count": 30})
    )

    assert client.detail_calls == 24


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
    assert {field.name for field in descriptor.filters} >= {
        "site",
        "period",
        "sort",
        "sfw",
        "tag",
    }
    assert provider.download(item, tmp_path).files == (
        "ty-image-spider/civitai/101.png",
    )


def test_civitai_legacy_tags_remain_available_and_map_to_api_ids(tmp_path):
    expected = {
        "Anime": 4,
        "Beach": 5998,
        "Fantasy": 5207,
        "Portrait": 1441,
        "Landscape": 8363,
    }
    client = FakeClient()
    provider = make_provider(tmp_path, client)
    field = next(field for field in provider.descriptor().filters if field.name == "tag")

    assert {option.value for option in field.options} == {"", *expected}
    for name, tag_id in expected.items():
        provider.search(SearchRequest("civitai", filters={"tag": name}))
        assert client.calls[-1][1]["tags"] == tag_id
