from io import BytesIO
from pathlib import Path

import pytest

from ty_image_spider.models import SpiderError
from ty_image_spider.security import (
    read_limited,
    redact_secrets,
    require_https_host,
    resolve_inside,
)


class Response(BytesIO):
    def __init__(self, payload: bytes, content_length: str | None = None):
        super().__init__(payload)
        self.headers = {"Content-Length": content_length} if content_length else {}


def test_redaction_is_recursive_and_case_insensitive():
    value = {
        "Cookie": "a",
        "nested": [{"xsec_token": "b", "label": "保留"}],
        "authorization": "Bearer c",
    }

    assert redact_secrets(value) == {
        "Cookie": "[已隐藏]",
        "nested": [{"xsec_token": "[已隐藏]", "label": "保留"}],
        "authorization": "[已隐藏]",
    }


def test_require_https_host_rejects_http_and_suffix_tricks():
    allowed = lambda host: host == "civitai.com" or host.endswith(".civitai.com")

    assert (
        require_https_host("https://image.civitai.com/a.jpg", allowed).hostname
        == "image.civitai.com"
    )
    with pytest.raises(SpiderError, match="不属于"):
        require_https_host("http://image.civitai.com/a.jpg", allowed)
    with pytest.raises(SpiderError, match="不属于"):
        require_https_host("https://civitai.com.evil.example/a.jpg", allowed)


def test_resolve_inside_rejects_escape_and_absolute_path(tmp_path):
    assert (
        resolve_inside(tmp_path, Path("folder/image.png"))
        == (tmp_path / "folder/image.png").resolve()
    )
    with pytest.raises(SpiderError, match="输出目录"):
        resolve_inside(tmp_path, Path("../escape.png"))
    with pytest.raises(SpiderError, match="输出目录"):
        resolve_inside(tmp_path, Path("C:/escape.png"))


def test_read_limited_checks_header_and_stream_size():
    with pytest.raises(SpiderError, match="大小限制"):
        read_limited(Response(b"12345", "5"), max_bytes=4)
    with pytest.raises(SpiderError, match="大小限制"):
        read_limited(Response(b"12345"), max_bytes=4)
    assert read_limited(Response(b"1234"), max_bytes=4) == b"1234"
