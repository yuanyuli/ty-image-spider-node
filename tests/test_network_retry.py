"""只重试可恢复网络故障；格式与身份错误立即返回。"""

import io
from datetime import datetime, timezone
from email.message import Message
from http.client import IncompleteRead
from urllib.error import HTTPError

import pytest

from ty_image_spider.network_retry import retry_call, retry_delay
from ty_image_spider.models import SpiderError
from ty_image_spider.providers.public_json_client import PublicJsonClient
from ty_image_spider.providers.museum_client import MuseumClient
from ty_image_spider.providers.curated_client import FilmGrabClient


def error(code, delay=None):
    headers = Message()
    if delay is not None:
        headers["Retry-After"] = delay
    return HTTPError(
        "https://example.invalid/?token=private", code, "failure", headers, None
    )


@pytest.mark.parametrize(
    "failure",
    [
        error(429, "2"),
        error(503),
        TimeoutError(),
        ConnectionResetError(),
        IncompleteRead(b""),
    ],
)
def test_transient_failure_retries_with_bounded_wait(failure):
    calls, delays = [], []

    def operation():
        calls.append(1)
        if len(calls) == 1:
            raise failure
        return "ok"

    assert retry_call(operation, sleep=delays.append) == "ok"
    assert len(calls) == 2 and len(delays) == 1
    assert 0 <= delays[0] <= 30


@pytest.mark.parametrize(
    "failure",
    [
        error(400),
        error(401),
        error(403),
        error(404),
        ValueError(),
        SpiderError("unsafe_url", "拒绝"),
    ],
)
def test_permanent_errors_do_not_retry(failure):
    calls = []

    def operation():
        calls.append(1)
        raise failure

    with pytest.raises(type(failure)):
        retry_call(operation, sleep=lambda _: pytest.fail("不应等待"))
    assert len(calls) == 1


def test_attempt_limit_and_http_date():
    calls, delays = [], []

    def operation():
        calls.append(1)
        raise error(503, "999999")

    with pytest.raises(HTTPError):
        retry_call(operation, sleep=delays.append)
    assert len(calls) == 3 and delays == [30, 30]
    now = datetime(2026, 9, 20, tzinfo=timezone.utc).timestamp()
    assert retry_delay(error(429, "Sun, 20 Sep 2026 00:00:10 GMT"), 0, now=now) == 10
    assert retry_delay(error(429, "NaN"), 0) == 1


class Response(io.BytesIO):
    headers = {}

    def __init__(self, data, url):
        super().__init__(data)
        self.url = url

    def geturl(self):
        return self.url


@pytest.mark.parametrize("source", ["public", "museum", "film"])
def test_client_retries_503_but_not_malformed_json(source, monkeypatch):
    monkeypatch.setattr("ty_image_spider.network_retry.time.sleep", lambda _: None)
    calls = []

    def open_url(request, **kwargs):
        calls.append(request)
        if len(calls) == 1:
            raise error(503)
        return Response(b"{", request.full_url)

    if source == "public":
        client = PublicJsonClient("https://example.invalid/", "测试", open_url=open_url)
        run = lambda: client.get("posts", {})
    elif source == "museum":
        client = MuseumClient("artic", open_url=open_url)
        run = lambda: client.get("artworks", {})
    else:
        client = FilmGrabClient(open_url=open_url)
        run = lambda: client.posts("", 1)
    with pytest.raises(SpiderError):
        run()
    assert len(calls) == 2
