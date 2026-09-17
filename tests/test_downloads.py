from io import BytesIO
import pytest
from PIL import Image

from ty_image_spider.downloads import ImageDownloader
from ty_image_spider.models import SpiderError


def png_bytes():
    output = BytesIO()
    Image.new("RGB", (3, 2), (255, 0, 0)).save(output, format="PNG")
    return output.getvalue()


class Response:
    def __init__(self, payload, final_url, content_type="image/png"):
        self.payload = payload
        self.final_url = final_url
        self.headers = {
            "Content-Length": str(len(payload)),
            "Content-Type": content_type,
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


def test_image_downloader_writes_verified_image_inside_output(tmp_path):
    url = "https://image.civitai.com/assets/cat.png"
    timeouts = []

    def open_url(request, *, timeout):
        timeouts.append(timeout)
        return Response(png_bytes(), request.full_url)

    downloader = ImageDownloader(open_url=open_url)

    result = downloader.download(url, "101", tmp_path)

    assert result.files == ("ty-image-spider/civitai/101.png",)
    saved = tmp_path / result.files[0]
    assert saved.is_file()
    with Image.open(saved) as image:
        assert image.size == (3, 2)
    assert timeouts == [60]


def test_image_downloader_rejects_untrusted_url_and_item_id(tmp_path):
    downloader = ImageDownloader(open_url=lambda *_: pytest.fail("不应访问网络"))
    with pytest.raises(SpiderError, match="素材源"):
        downloader.download("https://evil.example/a.png", "1", tmp_path)
    with pytest.raises(SpiderError, match="素材 ID"):
        downloader.download("https://image.civitai.com/a.png", "../escape", tmp_path)


def test_image_downloader_rejects_cross_domain_redirect(tmp_path):
    downloader = ImageDownloader(
        open_url=lambda *_, **__: Response(png_bytes(), "https://evil.example/a.png")
    )
    with pytest.raises(SpiderError, match="重定向"):
        downloader.download("https://image.civitai.com/a.png", "1", tmp_path)


def test_image_downloader_cleans_temp_file_after_invalid_payload(tmp_path):
    url = "https://image.civitai.com/assets/not-image.png"
    downloader = ImageDownloader(open_url=lambda *_, **__: Response(b"not image", url))

    with pytest.raises(SpiderError, match="有效图片"):
        downloader.download(url, "1", tmp_path)

    target = tmp_path / "ty-image-spider/civitai"
    assert not list(target.glob("*.tmp"))
    assert not list(target.glob("1.*"))
