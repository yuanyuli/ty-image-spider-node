from pathlib import Path

from ty_image_spider.api import ROUTES
from ty_image_spider.app import build_services


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


def test_runtime_entrypoints_are_idempotent():
    from ty_image_spider.api import ROUTES, register_routes
    from ty_image_spider.app import TyImageSpider, build_services

    assert len(ROUTES) == 11
    assert register_routes() in {True, False}
    assert TyImageSpider.FUNCTION == "browse"
    assert callable(build_services)


def test_provider_category_packages_export_composition_types():
    from ty_image_spider.providers.collections import ArticProvider, NasaProvider
    from ty_image_spider.providers.editorial import ArenaProvider, BehanceProvider
    from ty_image_spider.providers.local import LocalProvider
    from ty_image_spider.providers.movies import FilmGrabProvider, TmdbImageProvider
    from ty_image_spider.providers.shared import ProviderRegistry, PublicJsonClient

    assert all(
        value is not None
        for value in (
            ArticProvider,
            NasaProvider,
            ArenaProvider,
            BehanceProvider,
            LocalProvider,
            FilmGrabProvider,
            TmdbImageProvider,
            ProviderRegistry,
            PublicJsonClient,
        )
    )


def test_large_provider_packages_have_separate_adapters():
    root = Path("src/ty_image_spider/providers")
    for relative in (
        "ai/civitai/client.py",
        "ai/civitai/normalizer.py",
        "ai/xiaohongshu/extract.py",
        "wallpapers/wallhaven/client.py",
        "wallpapers/netbian/parser.py",
        "wallpapers/bizhi99/parser.py",
        "wallpapers/wallpaperscraft/parser.py",
    ):
        assert (root / relative).is_file(), relative


def test_frontend_entrypoint_only_composes_extension():
    entry = Path("web/ty_image_spider.js")

    assert len(entry.read_text("utf-8").splitlines()) <= 40
