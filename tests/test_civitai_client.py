import json
from pathlib import Path
from urllib.error import HTTPError

import pytest

from ty_image_spider.models import SpiderError
from ty_image_spider.providers.civitai_client import CivitaiClient


FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures/civitai_images.json").read_text()
)


class Response:
    def __init__(self, payload, final_url="https://civitai.com/api/v1/images"):
        self.payload = json.dumps(payload).encode()
        self.headers = {
            "Content-Type": "application/json",
            "Content-Length": str(len(self.payload)),
        }
        self.final_url = final_url

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self, _size=-1):
        payload, self.payload = self.payload, b""
        return payload

    def geturl(self):
        return self.final_url


def test_client_builds_query_and_keeps_api_key_out_of_url():
    requests = []

    def open_url(request, timeout):
        requests.append((request, timeout))
        return Response(FIXTURE)

    client = CivitaiClient(open_url=open_url, api_key="top-secret")
    page = client.search(
        "civitai.com", {"query": "red cat", "limit": 6, "nsfw": "None"}
    )

    assert page.next_cursor == "cursor-2"
    assert page.items[0]["id"] == 101
    assert "query=red+cat" in requests[0][0].full_url
    assert "top-secret" not in requests[0][0].full_url
    assert requests[0][0].get_header("Authorization") == "Bearer top-secret"
    assert requests[0][1] == 30


def test_client_retries_429_using_retry_after():
    calls = 0
    sleeps = []

    def open_url(request, timeout):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise HTTPError(
                request.full_url, 429, "limited", {"Retry-After": "2"}, None
            )
        return Response(FIXTURE)

    page = CivitaiClient(open_url=open_url, sleep=sleeps.append).search(
        "civitai.red", {}
    )

    assert page.items
    assert calls == 2
    assert sleeps == [2.0]


def test_client_maps_forbidden_without_retry():
    def open_url(request, timeout):
        raise HTTPError(request.full_url, 403, "forbidden", {}, None)

    with pytest.raises(SpiderError) as caught:
        CivitaiClient(open_url=open_url).search("civitai.com", {})

    assert caught.value.code == "civitai_forbidden"
    assert caught.value.status == 403


def test_client_rejects_unknown_site_before_network():
    with pytest.raises(SpiderError, match="站点"):
        CivitaiClient(open_url=lambda *_: pytest.fail("不应访问网络")).search(
            "evil.example", {}
        )
