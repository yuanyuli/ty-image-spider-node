from pathlib import Path

from ty_image_spider.bootstrap import build_services
from ty_image_spider.routes import ROUTES


EXPECTED_ROUTES = (
    ("GET", "/ty-image-spider/providers"),
    ("POST", "/ty-image-spider/search"),
    ("POST", "/ty-image-spider/detail"),
    ("POST", "/ty-image-spider/download"),
    ("POST", "/ty-image-spider/download-image"),
    ("POST", "/ty-image-spider/download-page"),
    ("POST", "/ty-image-spider/providers/xiaohongshu/check"),
    ("POST", "/ty-image-spider/providers/xiaohongshu/connect"),
    ("POST", "/ty-image-spider/cache/start"),
    ("GET", "/ty-image-spider/cache/{job_id}"),
    ("POST", "/ty-image-spider/cache/{job_id}/cancel"),
)


def test_public_route_and_provider_contracts_are_stable(tmp_path):
    assert tuple((method, path) for method, path, _ in ROUTES) == EXPECTED_ROUTES
    services = build_services(tmp_path / "output", tmp_path / "cache")
    descriptors = services.providers.descriptors()
    assert len(descriptors) == 24
    assert sum(item.presentation.visible for item in descriptors) == 23
    assert [item.id for item in descriptors] == list(
        __import__("json").loads(
            Path("tests/fixtures/provider_descriptors.json").read_text("utf-8")
        )
    )
