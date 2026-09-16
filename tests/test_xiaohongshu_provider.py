import json
import threading
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from ty_image_spider.cache import JsonCache
from ty_image_spider.models import AssetItem, SearchRequest, SpiderError
from ty_image_spider.providers.xiaohongshu import XiaohongshuProvider
from ty_image_spider.providers.xiaohongshu_extract import build_card_extract_js


FIXTURES = Path(__file__).parent / "fixtures"
SEARCH = json.loads((FIXTURES / "xiaohongshu_search.json").read_text(encoding="utf-8"))
CARDS = json.loads((FIXTURES / "xiaohongshu_cards.json").read_text(encoding="utf-8"))
DETAIL = json.loads((FIXTURES / "xiaohongshu_detail.json").read_text(encoding="utf-8"))


class Call:
    def __init__(self, args, timeout_seconds):
        self.args = args
        self.timeout_seconds = timeout_seconds


class FakeRunner:
    def __init__(self, responses=None, error=None, on_call=None):
        self.responses = list(responses or [])
        self.error = error
        self.on_call = on_call
        self.calls = []

    def version(self):
        if self.error:
            raise self.error
        return "1.8.8"

    def doctor(self):
        if self.error:
            raise self.error
        return object()

    def run_json(self, args, timeout_seconds):
        self.calls.append(Call(list(args), timeout_seconds))
        if self.error:
            raise self.error
        if self.on_call:
            self.on_call(args)
        return self.responses.pop(0) if self.responses else {}


def make_provider(tmp_path, runner=None):
    return XiaohongshuProvider(
        runner or FakeRunner([SEARCH, CARDS]),
        JsonCache(tmp_path / "cache"),
        threading.Lock(),
    )


def xhs_item(url):
    return AssetItem(
        "xiaohongshu",
        "66abcdef1234567890abcdef",
        source_url=url,
        preview_url="https://sns-img-bd.xhscdn.com/detail-one.webp",
        download_mode="note",
    )


def test_search_uses_official_adapter_then_persistent_read_only_eval(tmp_path):
    runner = FakeRunner([SEARCH, CARDS])
    page = make_provider(tmp_path, runner).search(
        SearchRequest(
            "xiaohongshu",
            "秋季穿搭",
            {
                "sort": "most-liked",
                "note_type": "image",
                "publish_time": "week",
                "count": 12,
            },
        )
    )

    assert runner.calls[0].args[:3] == ["xiaohongshu", "search", "秋季穿搭"]
    assert runner.calls[0].args[-10:] == [
        "--limit",
        "12",
        "--sort",
        "most-liked",
        "--note-type",
        "image",
        "--publish-time",
        "week",
        "--format",
        "json",
    ]
    assert "--site-session" in runner.calls[0].args
    assert runner.calls[1].args[:4] == [
        "browser",
        "site:xiaohongshu",
        "eval",
        build_card_extract_js(),
    ]
    assert page.items[0].preview_url.startswith("https://sns-img")
    assert page.items[0].image_count == 4
    assert page.items[0].download_mode == "note"


def test_signed_note_url_uses_note_flow_instead_of_keyword_search(tmp_path):
    url = (
        "https://www.xiaohongshu.com/explore/66abcdef1234567890abcdef?xsec_token=signed"
    )
    runner = FakeRunner([DETAIL["rows"], DETAIL["browser"]])

    page = make_provider(tmp_path, runner).search(SearchRequest("xiaohongshu", url))

    assert runner.calls[0].args[:3] == ["xiaohongshu", "note", url]
    assert page.items[0].source_url == url
    assert page.items[0].title == "秋季通勤穿搭"
    assert page.items[0].image_count == 2


def test_search_rejects_untrusted_http_url(tmp_path):
    with pytest.raises(SpiderError) as caught:
        make_provider(tmp_path).search(
            SearchRequest("xiaohongshu", "https://evil.example/a")
        )
    assert caught.value.code == "invalid_note_url"


def test_detail_rejects_unsigned_note_url(tmp_path):
    item = xhs_item("https://www.xiaohongshu.com/explore/66abcdef1234567890abcdef")
    with pytest.raises(SpiderError, match="完整签名链接"):
        make_provider(tmp_path).detail(item)


def test_keyword_cache_never_persists_signed_urls(tmp_path):
    make_provider(tmp_path).search(SearchRequest("xiaohongshu", "秋季穿搭"))

    cache_text = "".join(
        path.read_text(encoding="utf-8") for path in (tmp_path / "cache").glob("*.json")
    )
    assert "xsec_token" not in cache_text
    assert "signed-one" not in cache_text


def test_detail_returns_ordered_images_and_content(tmp_path):
    runner = FakeRunner([DETAIL["rows"], DETAIL["browser"]])
    item = xhs_item(SEARCH[0]["url"])

    detail = make_provider(tmp_path, runner).detail(item)

    assert detail.images == tuple(DETAIL["browser"]["images"])
    assert detail.content == "三套适合上班的叠穿思路"
    assert detail.item.stats == {"likes": "128", "collects": "32", "comments": "9"}


def test_download_returns_only_new_verified_images(tmp_path):
    output = tmp_path / "output"

    def write_download(args):
        if args[:2] != ["xiaohongshu", "download"]:
            return
        parent = Path(args[args.index("--output") + 1])
        target = parent / "66abcdef1234567890abcdef"
        target.mkdir(parents=True, exist_ok=True)
        buffer = BytesIO()
        Image.new("RGB", (3, 2), (200, 20, 20)).save(buffer, format="PNG")
        (target / "image-1.png").write_bytes(buffer.getvalue())
        (target / "not-image.txt").write_text("ignore", encoding="utf-8")

    runner = FakeRunner([[]], on_call=write_download)
    result = make_provider(tmp_path, runner).download(
        xhs_item(SEARCH[0]["url"]), output
    )

    assert result.files == (
        "ty-image-spider/xiaohongshu/66abcdef1234567890abcdef/image-1.png",
    )
    assert "--site-session" in runner.calls[0].args


def test_status_exposes_optional_dependency_failure(tmp_path):
    runner = FakeRunner(
        error=SpiderError("opencli_missing", "未找到 OpenCLI", status=503)
    )

    status = make_provider(tmp_path, runner).status()

    assert status.available is False
    assert status.code == "opencli_missing"
