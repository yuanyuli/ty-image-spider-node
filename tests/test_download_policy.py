from io import BytesIO

import pytest
from PIL import Image

from ty_image_spider.models import SpiderError
from ty_image_spider.providers import curated_download


def test_new_source_policy_needs_no_central_mapping(tmp_path):
    from ty_image_spider.providers.download_policy import HostDownloadPolicy
    from ty_image_spider.providers.image_readers import ImageReaderRegistry

    policy = HostDownloadPolicy(
        "newsource", lambda host: host == "images.example.org", r"[0-9]+", "/%,!"
    )
    payload = BytesIO()
    Image.new("RGB", (10, 10)).save(payload, "PNG")
    url = "https://images.example.org/full/843,/0/default.png"

    class Response(BytesIO):
        headers = {}

        def geturl(self):
            return url

    seen = []

    def open_url(request, **kwargs):
        seen.append(request.full_url)
        return Response(payload.getvalue())

    downloader = curated_download.CuratedDownloader(policy, open_url)
    readers = ImageReaderRegistry()
    readers.register(policy.provider_id, downloader)
    assert readers.read(url, "newsource")[1] == ".png"
    result = downloader.download(url, "123", tmp_path)
    assert result.files == ("ty-image-spider/newsource/123.png",)
    assert seen == [url, url]
    for bad in ("../123", "12/3", "12\\3", "123."):
        with pytest.raises(SpiderError):
            downloader.download(url, bad, tmp_path)
    with pytest.raises(SpiderError):
        readers.read(url, "unknown")
    with pytest.raises(ValueError):
        readers.register("newsource", downloader)


def test_download_policy_rejects_credentials_and_non_https():
    from ty_image_spider.providers.download_policy import HostDownloadPolicy

    policy = HostDownloadPolicy(
        "newsource", lambda host: host == "images.example.org", r"[0-9]+"
    )
    for url in (
        "http://images.example.org/1.jpg",
        "https://images.example.org.evil.test/1.jpg",
        "https://user:secret@images.example.org/1.jpg",
        "https://images.example.org:8443/1.jpg",
    ):
        with pytest.raises(SpiderError):
            policy.validate_url(url)
