import json
from pathlib import Path
from urllib.error import HTTPError

import pytest

from ty_image_spider.models import SpiderError
from ty_image_spider.providers.wallhaven_client import WallhavenClient


FIXTURES = Path(__file__).parent / "fixtures"
SEARCH = json.loads((FIXTURES / "wallhaven_search.json").read_text())
DETAIL = json.loads((FIXTURES / "wallhaven_detail.json").read_text())


class Response:
    def __init__(self, payload, final_url):
        self.payload = json.dumps(payload).encode()
        self.final_url = final_url
        self.headers = {"Content-Length": str(len(self.payload))}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self, size=-1):
        payload, self.payload = self.payload, b""
        return payload

    def geturl(self):
        return self.final_url


def test_wallhaven_client_builds_search_query_and_page_metadata():
    requests = []

    def open_url(request, timeout):
        requests.append((request, timeout))
        return Response(SEARCH, request.full_url)

    page = WallhavenClient(open_url=open_url).search(
        {"q": "red cat", "categories": "101", "purity": "100", "page": 2}
    )

    assert page.items[0]["id"] == "zp9vkg"
    assert page.current_page == 1
    assert page.last_page == 3
    assert "q=red+cat" in requests[0][0].full_url
    assert "categories=101" in requests[0][0].full_url
    assert requests[0][1] == 30


def test_wallhaven_client_reads_detail_and_rejects_invalid_id():
    client = WallhavenClient(
        open_url=lambda request, timeout: Response(DETAIL, request.full_url)
    )

    detail = client.detail("zp9vkg")

    assert detail["uploader"]["username"] == "wall-user"
    with pytest.raises(SpiderError) as caught:
        client.detail("../bad")
    assert caught.value.code == "invalid_asset"


def test_wallhaven_client_maps_rate_limit():
    def open_url(request, timeout):
        raise HTTPError(request.full_url, 429, "limited", {}, None)

    with pytest.raises(SpiderError) as caught:
        WallhavenClient(open_url=open_url, max_retries=0).search({})

    assert caught.value.code == "wallhaven_rate_limited"
    assert caught.value.status == 429
