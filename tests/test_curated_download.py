from io import BytesIO

import pytest
from PIL import Image

from ty_image_spider.models import SpiderError
from ty_image_spider.providers.curated_download import CuratedDownloader


@pytest.mark.parametrize(
    "provider,item_id,url",
    [
        (
            "colossal",
            "42-1",
            "https://www.thisiscolossal.com/wp-content/uploads/image.jpg",
        ),
        ("designmilk", "42-1", "https://design-milk.com/images/image.jpg"),
        ("arena", "42", "https://d2w9rnfcy7mm78.cloudfront.net/42/image.jpg"),
        (
            "artic",
            "27992",
            "https://www.artic.edu/iiif/2/image/full/843,/0/default.jpg",
        ),
        (
            "vam",
            "O499248",
            "https://framemark.vam.ac.uk/collections/2007BP5642/full/full/0/default.jpg",
        ),
        (
            "cleveland",
            "160087",
            "https://openaccess-cdn.clevelandart.org/1997.56/1997.56_print.jpg",
        ),
    ],
)
def test_museum_download_saves_valid_image_under_its_own_source(
    tmp_path, provider, item_id, url
):
    data = BytesIO()
    Image.new("RGB", (12, 8)).save(data, "JPEG")
    downloader = CuratedDownloader(lambda *a, **k: Response(data.getvalue(), url))
    result = downloader.download(url, provider, item_id, tmp_path)
    assert result.files == (f"ty-image-spider/{provider}/{item_id}.jpg",)
    assert (tmp_path / result.files[0]).is_file()
    with pytest.raises(SpiderError):
        downloader.download(url, provider, "../../secret", tmp_path)
    with pytest.raises(SpiderError):
        downloader.read("https://example.com/image.jpg", provider)


class Response(BytesIO):
    headers = {}

    def __init__(self, payload, url):
        super().__init__(payload)
        self.url = url

    def geturl(self):
        return self.url


def test_existing_valid_image_is_reused_without_network(tmp_path):
    target = tmp_path / "ty-image-spider" / "colossal" / "42-1.jpg"
    target.parent.mkdir(parents=True)
    Image.new("RGB", (16, 12)).save(target)

    def unexpected(*args, **kwargs):
        pytest.fail("已有有效图片不应重新联网")

    saved = CuratedDownloader(unexpected).download(
        "https://www.thisiscolossal.com/image.jpg", "colossal", "42-1", tmp_path
    )
    assert saved.files == ("ty-image-spider/colossal/42-1.jpg",)


def test_corrupt_existing_image_is_replaced(tmp_path):
    target = tmp_path / "ty-image-spider" / "colossal" / "42-1.jpg"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"broken")
    data = BytesIO()
    Image.new("RGB", (16, 12)).save(data, "JPEG")
    url = "https://www.thisiscolossal.com/image.jpg"
    CuratedDownloader(lambda *a, **k: Response(data.getvalue(), url)).download(
        url, "colossal", "42-1", tmp_path
    )
    with Image.open(target) as image:
        assert image.size == (16, 12)


def test_iiif_size_syntax_is_not_percent_encoded():
    image = BytesIO()
    Image.new("RGB", (8, 8)).save(image, "PNG")
    url = "https://www.artic.edu/iiif/2/image/full/843,/0/default.jpg"

    def read(request, **kwargs):
        assert request.full_url == url
        return Response(image.getvalue(), url)

    CuratedDownloader(read).read(url, "artic")


def test_curated_download_verifies_actual_image_and_saves_under_source(tmp_path):
    data = BytesIO()
    Image.new("RGB", (12, 8)).save(data, "PNG")
    url = "https://film-grab.com/wp-content/uploads/photo-gallery/test.jpg"
    downloader = CuratedDownloader(
        lambda *args, **kwargs: Response(data.getvalue(), url)
    )
    result = downloader.download(url, "filmgrab", "12-77", tmp_path)
    assert result.files == ("ty-image-spider/filmgrab/12-77.png",)
    with Image.open(tmp_path / result.files[0]) as image:
        assert image.size == (12, 8)


def test_curated_download_rejects_untrusted_urls_before_fetching():
    def unexpected(*args, **kwargs):
        raise AssertionError("不应请求不受信任的域名")

    downloader = CuratedDownloader(unexpected)
    with pytest.raises(SpiderError):
        downloader.read("https://example.com/test.jpg", "behance")


def test_curated_download_rejects_html_and_cross_site_redirect():
    url = "https://film-grab.com/test.jpg"
    downloader = CuratedDownloader(
        lambda *args, **kwargs: Response(b"<html>blocked</html>", url)
    )
    with pytest.raises(SpiderError, match="有效图片"):
        downloader.read(url, "filmgrab")
    downloader = CuratedDownloader(
        lambda *args, **kwargs: Response(b"image", "https://example.com/test.jpg")
    )
    with pytest.raises(SpiderError):
        downloader.read(url, "filmgrab")


def test_curated_download_encodes_old_filmgrab_filenames_without_double_encoding():
    image = BytesIO()
    Image.new("RGB", (8, 8)).save(image, "PNG")
    expected = "https://film-grab.com/wp-content/uploads/photo-gallery/01%20%28155%29%20%C3%A9.jpg?bwg=12%203"

    def open_url(request, **kwargs):
        assert request.full_url == expected
        return Response(image.getvalue(), expected)

    downloader = CuratedDownloader(open_url)
    downloader.read(
        "https://film-grab.com/wp-content/uploads/photo-gallery/01 (155) é.jpg?bwg=12%203",
        "filmgrab",
    )
