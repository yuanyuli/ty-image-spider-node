import pytest

from ty_image_spider.models import (
    AssetDetail,
    AssetItem,
    DownloadResult,
    ProviderStatus,
    SearchPage,
    SearchRequest,
    SpiderError,
)


def test_asset_item_serializes_without_none_values():
    item = AssetItem(
        provider="civitai",
        id="42",
        preview_url="https://image.civitai.com/a.jpg",
    )

    assert item.to_dict() == {
        "provider": "civitai",
        "id": "42",
        "kind": "image",
        "preview_url": "https://image.civitai.com/a.jpg",
        "has_prompt": False,
        "image_count": 1,
        "stats": {},
        "tags": [],
        "metadata": {},
        "download_mode": "single",
    }
    assert AssetItem.from_untrusted(item.to_dict()) == item


def test_asset_item_rejects_untrusted_shape():
    with pytest.raises(SpiderError, match="素材数据"):
        AssetItem.from_untrusted({"provider": "local", "id": ["not-a-string"]})


def test_domain_results_serialize_nested_values():
    item = AssetItem(provider="local", id="a", title="a.png", download_mode="none")
    detail = AssetDetail(item=item, images=("/view?a",), content="正文")
    page = SearchPage(items=(item,), next_cursor="10", stale=True, message="缓存")
    download = DownloadResult(files=("ty-image-spider/a.png",), message="完成")
    status = ProviderStatus(available=False, code="missing", message="未安装", action="安装")

    assert detail.to_dict()["item"]["id"] == "a"
    assert page.to_dict()["items"][0]["download_mode"] == "none"
    assert download.to_dict()["files"] == ["ty-image-spider/a.png"]
    assert status.to_dict() == {
        "available": False,
        "code": "missing",
        "message": "未安装",
        "action": "安装",
    }


def test_search_request_copies_mutable_filters():
    filters = {"count": 9}
    request = SearchRequest(provider="civitai", filters=filters)
    filters["count"] = 1

    assert request.filters == {"count": 9}

