from io import BytesIO
import json
import re
from urllib.parse import parse_qs, urlsplit

from ty_image_spider.models import DownloadResult, SearchRequest
from ty_image_spider.providers.nasa import NasaProvider
from ty_image_spider.providers.public_json_client import PublicJsonClient


class Response(BytesIO):
    headers = {}

    def __init__(self, data, url):
        super().__init__(json.dumps(data).encode())
        self.url = url

    def geturl(self):
        return self.url


def nasa_result(nasa_id="APOLLO 50th_FULL COLOR_300DPI"):
    root = f"https://images-assets.nasa.gov/image/{nasa_id}/{nasa_id}"
    return {
        "href": root + "/collection.json",
        "data": [
            {
                "album": ["Apollo at 50"],
                "center": "HQ",
                "date_created": "2018-06-18T00:00:00Z",
                "description": "Full color identity for the Apollo anniversary.",
                "keywords": ["Apollo", "anniversary", "logo"],
                "media_type": "image",
                "nasa_id": nasa_id,
                "photographer": "NASA Design",
                "title": "Apollo 50th Anniversary",
            }
        ],
        "links": [
            {
                "href": root + "~large.jpg",
                "rel": "alternate",
                "render": "image",
                "width": 12000,
                "height": 8000,
            },
            {
                "href": root + "~small.jpg",
                "rel": "alternate",
                "render": "image",
                "width": 640,
                "height": 398,
            },
            {
                "href": root + "~orig.png",
                "rel": "canonical",
                "render": "image",
                "width": 8400,
                "height": 5225,
            },
        ],
    }


def provider(payload, calls, downloader=None):
    def read(request, timeout):
        calls.append(request.full_url)
        return Response(payload, request.full_url)

    return NasaProvider(
        PublicJsonClient("https://images-api.nasa.gov/", "NASA", open_url=read),
        downloader,
    )


def test_nasa_search_maps_category_page_and_image_variants():
    calls = []
    payload = {
        "collection": {
            "metadata": {"total_hits": 49},
            "items": [nasa_result(), {"data": [{"nasa_id": "missing-image"}]}],
        }
    }
    page = provider(payload, calls).search(
        SearchRequest("nasa", "night", {"category": "moon"}, cursor="2")
    )

    query = parse_qs(urlsplit(calls[0]).query)
    assert query == {
        "media_type": ["image"],
        "page": ["2"],
        "page_size": ["24"],
        "q": ["moon night"],
    }
    assert page.next_cursor == "3" and len(page.items) == 1
    item = page.items[0]
    assert re.fullmatch(r"APOLLO-50th_FULL-COLOR_300DPI-[0-9a-f]{12}", item.id)
    assert item.preview_url.endswith("~small.jpg")
    assert item.metadata["original_url"].endswith("~orig.png")
    assert item.author == "NASA Design"
    assert item.tags == ("Apollo", "anniversary", "logo")
    assert item.source_url.endswith("APOLLO%2050th_FULL%20COLOR_300DPI")


def test_nasa_detail_and_download_keep_official_metadata(tmp_path):
    class Downloader:
        def __init__(self):
            self.call = None

        def download(self, url, source, item_id, output_root):
            self.call = (url, source, item_id, output_root)
            return DownloadResult((f"ty-image-spider/{source}/{item_id}.png",))

    downloader = Downloader()
    payload = {
        "collection": {
            "metadata": {"total_hits": 1},
            "items": [nasa_result("AS11-40-5903")],
        }
    }
    source = provider(payload, [], downloader)
    item = source.search(SearchRequest("nasa", filters={"category": "apollo"})).items[0]

    detail = source.detail(item)
    saved = source.download(item, tmp_path)

    assert item.id == "AS11-40-5903"
    assert detail.images == (item.metadata["original_url"],)
    assert detail.content == "Full color identity for the Apollo anniversary."
    assert item.metadata["collection"] == "NASA Image and Video Library"
    assert item.metadata["rights"] == "使用条件见 NASA 来源页面"
    assert downloader.call == (detail.images[0], "nasa", item.id, tmp_path)
    assert saved.files[0].endswith("AS11-40-5903.png")


def test_nasa_skips_cross_site_and_non_image_assets():
    row = nasa_result("SAFE-ID")
    row["links"] = [
        {
            "href": "https://evil.test/image.jpg",
            "rel": "canonical",
            "render": "image",
            "width": 2000,
            "height": 1000,
        },
        {
            "href": "https://images-assets.nasa.gov/image/SAFE-ID/metadata.json",
            "rel": "canonical",
            "render": "image",
            "width": 2000,
            "height": 1000,
        },
    ]
    payload = {"collection": {"metadata": {"total_hits": 1}, "items": [row]}}

    page = provider(payload, []).search(
        SearchRequest("nasa", filters={"category": "all"})
    )

    assert page.items == () and page.next_cursor is None
