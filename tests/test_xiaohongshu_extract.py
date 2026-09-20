import json
from pathlib import Path

from ty_image_spider.providers.xiaohongshu_extract import (
    build_card_extract_js,
    build_detail_extract_js,
    merge_search_rows,
)


FIXTURES = Path(__file__).parent / "fixtures"
ROWS = json.loads((FIXTURES / "xiaohongshu_search.json").read_text(encoding="utf-8"))
CARDS = json.loads((FIXTURES / "xiaohongshu_cards.json").read_text(encoding="utf-8"))


def test_merge_search_rows_uses_trusted_card_images_and_preserves_signed_url():
    items = merge_search_rows(ROWS, CARDS)

    assert [item["id"] for item in items] == [
        "66abcdef1234567890abcdef",
        "66abcdef1234567890abcdee",
    ]
    assert items[0]["preview_url"].startswith("https://sns-img-bd.xhscdn.com/")
    assert items[0]["image_count"] == 4
    assert "xsec_token=" in items[0]["source_url"]


def test_merge_ignores_untrusted_urls_and_images():
    rows = [{**ROWS[0], "url": "https://evil.example/note/66abcdef1234567890abcdef"}]
    cards = [{**CARDS[0], "preview_url": "https://evil.example/image.webp"}]

    assert merge_search_rows(rows, cards) == []
    assert merge_search_rows([ROWS[0]], cards)[0]["preview_url"] is None


def test_merge_skips_unsigned_note_links_that_cannot_open_detail_or_download():
    unsigned = {
        **ROWS[0],
        "url": "https://www.xiaohongshu.com/explore/66abcdef1234567890abcdef",
    }

    assert merge_search_rows([unsigned], []) == []


def test_browser_extract_scripts_are_read_only_and_detail_is_scoped():
    card_script = build_card_extract_js()
    detail_script = build_detail_extract_js("66abcdef1234567890abcdef")

    for script in (card_script, detail_script):
        assert "fetch(" not in script
        assert ".click(" not in script
        assert "location.href =" not in script
    assert "#noteContainer" in detail_script
    assert "noteDetailMap" in detail_script
    assert "66abcdef1234567890abcdef" in detail_script
