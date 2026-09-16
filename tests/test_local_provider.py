import os
from pathlib import Path

import pytest
from PIL import Image, PngImagePlugin

from ty_image_spider.models import SearchRequest, SpiderError
from ty_image_spider.providers.local import LocalProvider


def write_png(path: Path, prompt: str = "", mtime: int = 10) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    info = PngImagePlugin.PngInfo()
    if prompt:
        info.add_text("prompt", prompt)
    Image.new("RGB", (4, 3), (30, 60, 90)).save(path, pnginfo=info)
    os.utime(path, (mtime, mtime))


def test_local_provider_reads_new_and_legacy_directories_in_mtime_order(tmp_path):
    write_png(tmp_path / "ty-node" / "old.png", prompt="old", mtime=10)
    write_png(tmp_path / "ty-image-spider" / "new.png", prompt="new", mtime=20)

    page = LocalProvider(tmp_path).search(SearchRequest("local", "", {"count": 10}))

    assert [item.title for item in page.items] == ["new.png", "old.png"]
    assert [item.prompt for item in page.items] == ["new", "old"]
    assert all(item.download_mode == "none" for item in page.items)
    assert page.items[0].preview_url == (
        "/view?filename=new.png&subfolder=ty-image-spider&type=output"
    )


def test_local_provider_filters_and_paginates_with_offset_cursor(tmp_path):
    write_png(tmp_path / "ty-image-spider" / "cat-new.png", "blue cat", 30)
    write_png(tmp_path / "ty-image-spider" / "cat-old.png", "red cat", 20)
    write_png(tmp_path / "ty-image-spider" / "dog.png", "blue dog", 10)
    provider = LocalProvider(tmp_path)

    first = provider.search(SearchRequest("local", "cat", {"count": 1, "only_with_prompt": True}))
    second = provider.search(
        SearchRequest(
            "local",
            "cat",
            {"count": 1, "only_with_prompt": True},
            cursor=first.next_cursor,
        )
    )

    assert [item.title for item in first.items] == ["cat-new.png"]
    assert first.next_cursor == "1"
    assert [item.title for item in second.items] == ["cat-old.png"]
    assert second.next_cursor is None


def test_local_provider_detail_returns_metadata_and_cannot_download(tmp_path):
    write_png(tmp_path / "ty-image-spider" / "image.png", "portrait", 10)
    provider = LocalProvider(tmp_path)
    item = provider.search(SearchRequest("local")).items[0]

    detail = provider.detail(item)

    assert detail.item.id == item.id
    assert detail.images == (item.preview_url,)
    assert detail.metadata["width"] == 4
    with pytest.raises(SpiderError, match="无需下载"):
        provider.download(item, tmp_path)


def test_local_provider_does_not_follow_external_symlink(tmp_path):
    outside = tmp_path.parent / f"{tmp_path.name}-outside.png"
    write_png(outside)
    link = tmp_path / "ty-image-spider" / "link.png"
    link.parent.mkdir(parents=True)
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("当前环境不能创建符号链接")

    assert LocalProvider(tmp_path).search(SearchRequest("local")).items == ()
