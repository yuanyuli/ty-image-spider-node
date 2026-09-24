from io import BytesIO

import pytest
from PIL import Image

from ty_image_spider.domain import SpiderError
from ty_image_spider.providers.wallpapers.wallhaven.download import WallhavenDownloader


def png_bytes():
    output = BytesIO()
    Image.new("RGB", (4, 3), (0, 128, 255)).save(output, format="PNG")
    return output.getvalue()


class Response:
    def __init__(self, payload, final_url):
        self.payload = payload
        self.final_url = final_url
        self.headers = {
            "Content-Length": str(len(payload)),
            "Content-Type": "image/png",
        }

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self, size=-1):
        if not self.payload:
            return b""
        if size < 0:
            size = len(self.payload)
        chunk, self.payload = self.payload[:size], self.payload[size:]
        return chunk

    def geturl(self):
        return self.final_url


def test_wallhaven_downloader_writes_verified_image(tmp_path):
    url = "https://w.wallhaven.cc/full/zp/wallhaven-zp9vkg.png"
    timeouts = []

    def open_url(request, *, timeout):
        timeouts.append(timeout)
        return Response(png_bytes(), request.full_url)

    downloader = WallhavenDownloader(open_url=open_url)

    result = downloader.download(url, "zp9vkg", tmp_path)

    assert result.files == ("ty-image-spider/wallhaven/zp9vkg.png",)
    assert (tmp_path / result.files[0]).is_file()
    assert timeouts == [60]


def test_wallhaven_downloader_reuses_existing_valid_image_without_network(tmp_path):
    target = tmp_path / "ty-image-spider/wallhaven/zp9vkg.png"
    target.parent.mkdir(parents=True)
    target.write_bytes(png_bytes())
    downloader = WallhavenDownloader(
        open_url=lambda *_args, **_kwargs: pytest.fail("已有图片不应重新联网")
    )

    result = downloader.download(
        "https://w.wallhaven.cc/full/zp/wallhaven-zp9vkg.png", "zp9vkg", tmp_path
    )

    assert result.files == ("ty-image-spider/wallhaven/zp9vkg.png",)
    assert result.message == "图片已存在，已复用"
    assert [path.name for path in target.parent.iterdir()] == ["zp9vkg.png"]


def test_wallhaven_downloader_replaces_corrupt_existing_image_without_suffix(tmp_path):
    target = tmp_path / "ty-image-spider/wallhaven/zp9vkg.png"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"broken")
    url = "https://w.wallhaven.cc/full/zp/wallhaven-zp9vkg.png"
    downloader = WallhavenDownloader(
        open_url=lambda *_args, **_kwargs: Response(png_bytes(), url)
    )

    result = downloader.download(url, "zp9vkg", tmp_path)

    assert result.files == ("ty-image-spider/wallhaven/zp9vkg.png",)
    assert [path.name for path in target.parent.iterdir()] == ["zp9vkg.png"]
    with Image.open(target) as image:
        assert image.size == (4, 3)


def test_wallhaven_downloader_rejects_untrusted_host_id_and_redirect(tmp_path):
    downloader = WallhavenDownloader(open_url=lambda *_: pytest.fail("不应访问网络"))
    with pytest.raises(SpiderError, match="Wallhaven"):
        downloader.download("https://evil.example/a.png", "zp9vkg", tmp_path)
    with pytest.raises(SpiderError, match="ID"):
        downloader.download("https://w.wallhaven.cc/a.png", "../bad", tmp_path)

    redirected = WallhavenDownloader(
        open_url=lambda *_, **__: Response(png_bytes(), "https://evil.example/a.png")
    )
    with pytest.raises(SpiderError, match="重定向"):
        redirected.download("https://w.wallhaven.cc/a.png", "zp9vkg", tmp_path)
