import json
from io import BytesIO
from urllib.parse import parse_qs, urlsplit

import pytest

from ty_image_spider.models import SearchRequest, SpiderError
from ty_image_spider.providers.museum_client import MuseumClient
from ty_image_spider.providers.artic import ArticProvider
from ty_image_spider.providers.cleveland import ClevelandProvider
from ty_image_spider.providers.vam import VamProvider


class Response(BytesIO):
    def __init__(self, value, url):
        super().__init__(json.dumps(value).encode())
        self.url = url

    def geturl(self):
        return self.url


def client(provider, payloads, calls):
    def read(request, timeout):
        calls.append(parse_qs(urlsplit(request.full_url).query))
        return Response(payloads.pop(0), request.full_url)

    return MuseumClient(provider, open_url=read)


def test_artic_search_filters_photographs_and_keeps_pagination_with_missing_images():
    calls = []
    row = {
        "id": 27992,
        "title": "A Sunday",
        "image_id": "abcd-123",
        "is_public_domain": True,
        "artist_display": "Georges Seurat",
        "date_display": "1884–86",
        "medium_display": "Oil on canvas",
        "description": "<p>A &amp; B</p>",
        "artwork_type_title": "Painting",
    }
    provider = ArticProvider(
        client(
            "artic",
            [
                {
                    "data": [row, {"id": 2, "image_id": None}],
                    "pagination": {"total_pages": 2},
                },
                {"data": [{**row, "id": 3}], "pagination": {"total_pages": 2}},
            ],
            calls,
        )
    )
    first = provider.search(
        SearchRequest("artic", "portrait", {"category": "photography"})
    )
    params = json.loads(calls[0]["params"][0])
    assert params["q"] == "portrait"
    assert {"term": {"artwork_type_id": 2}} in params["query"]["bool"]["filter"]
    assert {"exists": {"field": "image_id"}} in params["query"]["bool"]["filter"]
    assert len(first.items) == 1 and first.next_cursor == "2"
    item = first.items[0]
    assert item.author == "Georges Seurat" and item.kind == "collection"
    assert item.metadata["rights"] == "CC0 / 公共领域"
    assert provider.detail(item).content == "A & B"
    assert "/full/1686,/" in provider.detail(item).images[0]
    last = provider.search(
        SearchRequest(
            "artic", "portrait", {"category": "photography"}, first.next_cursor
        )
    )
    assert last.items[0].id == "3" and last.next_cursor is None
    assert json.loads(calls[1]["params"][0])["page"] == 2


def test_cleveland_uses_skip_and_downloadable_jpeg_not_full_tiff():
    calls = []
    row = {
        "id": 160087,
        "title": "Self-Portrait",
        "type": "Photograph",
        "creation_date": "1843",
        "creators": [{"description": "Camille Dolard"}],
        "share_license_status": "CC0",
        "accession_number": "1997.56",
        "images": {
            "web": {
                "url": "https://openaccess-cdn.clevelandart.org/1997.56/1997.56_web.jpg"
            },
            "print": {
                "url": "https://openaccess-cdn.clevelandart.org/1997.56/1997.56_print.jpg"
            },
            "full": {
                "url": "https://openaccess-cdn.clevelandart.org/1997.56/1997.56_full.tif"
            },
        },
    }
    provider = ClevelandProvider(
        client("cleveland", [{"data": [row], "info": {"total": 25}}], calls)
    )
    page = provider.search(
        SearchRequest("cleveland", "portrait", {"category": "photography"}, "2")
    )
    assert calls[0]["skip"] == ["24"] and calls[0]["type"] == ["Photograph"]
    assert calls[0]["q"] == ["portrait"]
    assert page.next_cursor is None
    item = page.items[0]
    assert item.author == "Camille Dolard" and item.created_at == "1843"
    assert provider.detail(item).images[0].endswith("_print.jpg")


def test_vam_real_category_primary_image_and_enriched_description():
    calls = []
    row = {
        "systemNumber": "O499248",
        "_primaryTitle": "Upton Pyne",
        "objectType": "Photograph",
        "_primaryImageId": "2007BP5642",
        "_primaryMaker": {"name": "Jem Southam"},
        "_primaryDate": "1997",
        "_primaryPlace": "England",
        "_images": {"imageResolution": "high"},
    }
    provider = VamProvider(
        client(
            "vam",
            [
                {"records": [row], "info": {"pages": 2}},
                {
                    "record": {
                        "systemNumber": "O499248",
                        "summaryDescription": "<p>Landscape study</p>",
                        "materials": [{"text": "photographic paper"}],
                    }
                },
                {"records": [{**row, "systemNumber": "O499249"}], "info": {"pages": 2}},
            ],
            calls,
        )
    )
    page = provider.search(SearchRequest("vam", filters={"category": "photography"}))
    assert calls[0]["id_category"] == ["THES48910"]
    assert calls[0]["images_exist"] == ["1"] and page.next_cursor == "2"
    item = page.items[0]
    assert (
        item.id == "O499248"
        and item.source_url == "https://collections.vam.ac.uk/item/O499248/"
    )
    detail = provider.detail(item)
    assert detail.content == "Landscape study"
    assert detail.item.metadata["medium"] == "photographic paper"
    assert detail.images == (
        "https://framemark.vam.ac.uk/collections/2007BP5642/full/!1680,1680/0/default.jpg",
    )
    assert provider.search(SearchRequest("vam", cursor="2")).next_cursor is None
    assert calls[2]["page"] == ["2"]


@pytest.mark.parametrize(
    "provider_type,source",
    [(ArticProvider, "artic"), (VamProvider, "vam"), (ClevelandProvider, "cleveland")],
)
def test_museum_rejects_invalid_cursor_and_category_before_network(
    provider_type, source
):
    def unexpected(*args, **kwargs):
        pytest.fail("无效输入不应访问网络")

    provider = provider_type(MuseumClient(source, open_url=unexpected))
    with pytest.raises(SpiderError, match="页码"):
        provider.search(SearchRequest(source, cursor="../../secret"))
    with pytest.raises(SpiderError, match="分类"):
        provider.search(SearchRequest(source, filters={"category": "invalid"}))


def test_missing_or_untrusted_cleveland_image_is_skipped_without_losing_next_page():
    rows = [
        {"id": 1, "images": None},
        {"id": 2, "images": {"web": {"url": "http://127.0.0.1/private"}}},
    ]
    provider = ClevelandProvider(
        client("cleveland", [{"data": rows, "info": {"total": 50}}], [])
    )
    page = provider.search(SearchRequest("cleveland"))
    assert not page.items and page.next_cursor == "2"
