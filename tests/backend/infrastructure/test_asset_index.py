import json
import sqlite3

from ty_image_spider.infrastructure.asset_index import AssetIndex
from ty_image_spider.domain import AssetDetail, AssetItem, MediaResource


def test_index_persists_image_and_prompt_and_preserves_fresh_source_url(tmp_path):
    root = tmp_path / "output"
    index = AssetIndex(root)
    item = AssetItem(
        "civitai",
        "123",
        preview_url="https://civitai.red/old",
        prompt="soft light",
        has_prompt=True,
        metadata={"site": "civitai.red"},
    )
    index.store(
        AssetDetail(item, ("https://civitai.red/large",)),
        b"\x89PNG\r\n\x1a\n" + b"fake",
        ".png",
    )
    reopened = AssetIndex(root)
    fresh = AssetItem(
        "civitai",
        "123",
        preview_url="https://civitai.red/new",
        source_url="https://civitai.red/images/123",
        metadata={"site": "civitai.red"},
    )
    hit = reopened.overlay(fresh)
    assert hit.prompt == "soft light"
    assert hit.has_prompt
    assert hit.source_url == fresh.source_url
    assert hit.preview_url.startswith("/view?")


def test_index_separates_civitai_sites(tmp_path):
    index = AssetIndex(tmp_path)
    item = AssetItem("civitai", "123", metadata={"site": "civitai.red"})
    index.store(AssetDetail(item), b"abc", ".jpg")
    other = AssetItem("civitai", "123", metadata={"site": "civitai.com"})
    assert index.overlay(other) == other


def test_cached_detail_keeps_workflow_and_missing_files_miss(tmp_path):
    index = AssetIndex(tmp_path)
    item = AssetItem("civitai", "1", preview_url="https://image.civitai.com/image.png")
    workflow = {"nodes": [{"id": 1}]}
    index.store(
        AssetDetail(item, (item.preview_url,), workflow=workflow), b"image", ".png"
    )
    assert index.detail(item).workflow == workflow
    assert len(index.detail(item).images) == 1
    for path in (tmp_path / "ty-node/ty-image-spider/cache").glob("*.png"):
        path.unlink()
    assert index.detail(item) is None
    assert index.overlay(item) == item


def test_cached_preview_does_not_add_duplicate_thumbnail_to_original_gallery(tmp_path):
    index = AssetIndex(tmp_path)
    item = AssetItem("filmgrab", "12-77", preview_url="https://film-grab.com/thumb.jpg")
    index.store(
        AssetDetail(item, ("https://film-grab.com/original.jpg",)), b"image", ".jpg"
    )
    assert index.detail(item).images == ("https://film-grab.com/original.jpg",)


def test_index_round_trips_video_detail_without_rewriting_remote_media_url(tmp_path):
    root = tmp_path / "output"
    index = AssetIndex(root)
    item = AssetItem(
        "prelinger",
        "movie-1",
        kind="video",
        preview_url="https://archive.org/services/img/movie-1",
        duration_seconds=42,
    )
    resource = MediaResource(
        "video",
        "https://archive.org/download/movie-1/movie-1.mp4",
        "video/mp4",
        "playback",
        duration_seconds=42,
    )
    index.store(AssetDetail(item, media=(resource,)), b"image", ".jpg")

    restored = AssetIndex(root).detail(item)

    assert restored is not None
    assert restored.item.duration_seconds == 42
    assert restored.media == (resource,)
    assert restored.media[0].url == resource.url


def test_index_restores_legacy_image_detail_without_media_field(tmp_path):
    index = AssetIndex(tmp_path)
    item = AssetItem("local", "legacy", preview_url="https://example.com/legacy.jpg")
    index.store(AssetDetail(item, (item.preview_url,)), b"image", ".jpg")
    database = tmp_path / "ty-node" / "ty-image-spider" / "cache" / "index.sqlite3"
    with sqlite3.connect(database) as connection:
        row = connection.execute("SELECT key, detail_json FROM assets").fetchone()
        payload = json.loads(row[1])
        payload.pop("media", None)
        connection.execute(
            "UPDATE assets SET detail_json = ? WHERE key = ?",
            (json.dumps(payload), row[0]),
        )

    restored = index.detail(item)

    assert restored is not None
    assert restored.media == ()
    assert restored.images[0].startswith("/view?")
