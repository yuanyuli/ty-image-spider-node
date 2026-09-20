from http.client import IncompleteRead
from io import BytesIO
from urllib.parse import parse_qs, urlparse

import pytest

from ty_image_spider.models import SpiderError
from ty_image_spider.providers.curated_client import FilmGrabClient


class Response(BytesIO):
    headers = {"X-WP-TotalPages": "1"}

    def geturl(self):
        return "https://film-grab.com/wp-json/wp/v2/posts"


def test_curated_film_uses_verified_id_instead_of_full_text_search():
    def open_url(request, timeout):
        params = parse_qs(urlparse(request.full_url).query)
        assert params["include"] == ["37847"]
        assert "search" not in params
        return Response(b'[{"id":37847}]')

    assert FilmGrabClient(open_url).posts("Her", 1)[0][0]["id"] == 37847


def test_truncated_response_retries_once_then_returns_complete_payload():
    calls = []

    def open_url(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise IncompleteRead(b"{")
        return Response(b'[{"id":37847}]')

    assert FilmGrabClient(open_url).posts("Her", 1)[0][0]["id"] == 37847
    assert len(calls) == 2


def test_persistent_truncation_becomes_domain_error_for_cache_fallback():
    calls = []

    def open_url(*args, **kwargs):
        calls.append(1)
        raise IncompleteRead(b"{")

    with pytest.raises(SpiderError, match="暂时无法访问"):
        FilmGrabClient(open_url).posts("Her", 1)
    assert len(calls) == 3
