"""受限视频下载器的策略、签名和原子写入测试。"""

from __future__ import annotations

from io import BytesIO

import pytest

from ty_image_spider.domain import MediaResource, SpiderError
from ty_image_spider.infrastructure.video import (
    VideoDownloader,
    VideoDownloadPolicy,
    detect_video_extension,
    find_valid_video,
)


MP4 = b"\x00\x00\x00\x18ftypisom" + b"x" * 32
WEBM = b"\x1a\x45\xdf\xa3" + b"x" * 32
OGG = b"OggS" + b"x" * 32


class FakeResponse:
    def __init__(
        self,
        payload: bytes,
        *,
        url: str = "https://media.example.test/item.mp4",
        content_length: int | None = None,
        fail_after_first_read: bool = False,
    ) -> None:
        self._stream = BytesIO(payload)
        self._url = url
        self._fail_after_first_read = fail_after_first_read
        self._reads = 0
        self.headers = {}
        if content_length is not None:
            self.headers["Content-Length"] = str(content_length)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def geturl(self) -> str:
        return self._url

    def read(self, size: int = -1) -> bytes:
        self._reads += 1
        if self._fail_after_first_read and self._reads > 1:
            raise OSError("连接中断")
        return self._stream.read(size)


def _policy(max_bytes: int = 1024) -> VideoDownloadPolicy:
    return VideoDownloadPolicy(
        provider_id="video-test",
        host_rule=lambda host: host == "media.example.test",
        id_pattern=r"[a-z0-9-]+",
        max_bytes=max_bytes,
    )


def _resource(url: str = "https://media.example.test/item.mp4") -> MediaResource:
    return MediaResource("video", url, "video/mp4", "download")


@pytest.mark.parametrize(
    ("header", "extension"),
    [(MP4, ".mp4"), (WEBM, ".webm"), (OGG, ".ogv")],
)
def test_detect_video_extension_recognizes_supported_signatures(header, extension):
    assert detect_video_extension(header) == extension
    assert detect_video_extension(b"<!doctype html>") is None


@pytest.mark.parametrize(
    ("resource", "item_id", "code"),
    [
        (_resource("http://media.example.test/item.mp4"), "item", "unsafe_url"),
        (_resource("https://attacker.test/item.mp4"), "item", "unsafe_url"),
        (_resource(), "../item", "invalid_asset"),
    ],
)
def test_download_rejects_unsafe_url_and_invalid_id(tmp_path, resource, item_id, code):
    opened = False

    def open_url(*args, **kwargs):
        nonlocal opened
        opened = True
        return FakeResponse(MP4)

    with pytest.raises(SpiderError) as error:
        VideoDownloader(_policy(), open_url=open_url).download(
            resource, item_id, tmp_path
        )

    assert error.value.code == code
    assert not opened


def test_download_rejects_unsafe_redirect(tmp_path):
    response = FakeResponse(MP4, url="https://attacker.test/item.mp4")
    downloader = VideoDownloader(_policy(), open_url=lambda *a, **k: response)

    with pytest.raises(SpiderError) as error:
        downloader.download(_resource(), "item", tmp_path)

    assert error.value.code == "unsafe_redirect"
    assert not list(tmp_path.rglob("*.tmp"))


def test_download_rejects_declared_oversize_without_reading(tmp_path):
    response = FakeResponse(MP4, content_length=2048)
    downloader = VideoDownloader(
        _policy(max_bytes=64), open_url=lambda *a, **k: response
    )

    with pytest.raises(SpiderError) as error:
        downloader.download(_resource(), "item", tmp_path)

    assert error.value.code == "video_too_large"
    assert response._reads == 0


def test_download_counts_stream_when_content_length_is_missing(tmp_path):
    response = FakeResponse(MP4 + b"y" * 128)
    downloader = VideoDownloader(
        _policy(max_bytes=64), open_url=lambda *a, **k: response
    )

    with pytest.raises(SpiderError) as error:
        downloader.download(_resource(), "item", tmp_path)

    assert error.value.code == "video_too_large"
    assert not list(tmp_path.rglob(".item-*.tmp"))


def test_interrupted_download_removes_partial_file(tmp_path):
    payload = MP4 + b"y" * (1024 * 1024 + 4)
    response = FakeResponse(payload, fail_after_first_read=True)
    downloader = VideoDownloader(
        _policy(max_bytes=len(payload) + 1), open_url=lambda *a, **k: response
    )

    with pytest.raises(SpiderError) as error:
        downloader.download(_resource(), "item", tmp_path)

    assert error.value.code == "download_failed"
    assert not list(tmp_path.rglob(".item-*.tmp"))


def test_html_disguised_as_video_is_rejected(tmp_path):
    response = FakeResponse(b"<!doctype html><title>error</title>")
    downloader = VideoDownloader(_policy(), open_url=lambda *a, **k: response)

    with pytest.raises(SpiderError) as error:
        downloader.download(_resource(), "item", tmp_path)

    assert error.value.code == "invalid_video"
    assert not list(tmp_path.rglob("item.*"))


def test_download_atomically_replaces_damaged_canonical_file(tmp_path):
    directory = tmp_path / "ty-image-spider" / "video-test"
    directory.mkdir(parents=True)
    target = directory / "item.mp4"
    target.write_bytes(b"broken")
    downloader = VideoDownloader(_policy(), open_url=lambda *a, **k: FakeResponse(MP4))

    result = downloader.download(_resource(), "item", tmp_path)

    assert target.read_bytes() == MP4
    assert result.files == ("ty-image-spider/video-test/item.mp4",)
    assert result.output_root == str(tmp_path.resolve())
    assert not list(directory.glob(".item-*.tmp"))


def test_existing_valid_video_is_reused_without_network(tmp_path):
    directory = tmp_path / "ty-image-spider" / "video-test"
    directory.mkdir(parents=True)
    target = directory / "item.webm"
    target.write_bytes(WEBM)

    def unexpected_open(*args, **kwargs):
        raise AssertionError("复用已有视频时不应访问网络")

    result = VideoDownloader(_policy(), open_url=unexpected_open).download(
        _resource(), "item", tmp_path
    )

    assert find_valid_video(directory, "item") == target
    assert result.files == ("ty-image-spider/video-test/item.webm",)
    assert "复用" in result.message
