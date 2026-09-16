from dataclasses import FrozenInstanceError

import pytest

from ty_image_spider.bootstrap import ApplicationServices, build_services


def test_build_services_composes_three_independent_providers(tmp_path):
    services = build_services(tmp_path / "output", tmp_path / "cache")

    assert isinstance(services, ApplicationServices)
    assert [item.id for item in services.providers.descriptors()] == [
        "civitai",
        "xiaohongshu",
        "local",
    ]
    assert services.search is not services.detail
    with pytest.raises(FrozenInstanceError):
        services.search = object()


def test_build_services_creates_source_specific_cache_directories(tmp_path):
    cache_root = tmp_path / "cache"

    build_services(tmp_path / "output", cache_root)

    assert (cache_root / "civitai").is_dir()
    assert (cache_root / "xiaohongshu").is_dir()
