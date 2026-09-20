from dataclasses import FrozenInstanceError

import pytest

from ty_image_spider import models
from ty_image_spider.bootstrap import build_services


def test_presentation_serializes_and_is_immutable():
    value = models.ProviderPresentation(
        "collections",
        "艺术馆藏",
        "AIC",
        "芝加哥艺术博物馆",
        30,
        40,
        "新增100件馆藏",
        True,
    )
    descriptor = models.ProviderDescriptor("artic", "芝加哥艺术", presentation=value)
    assert descriptor.to_dict()["presentation"] == {
        "group_id": "collections",
        "group_label": "艺术馆藏",
        "short_label": "AIC",
        "detail_label": "芝加哥艺术博物馆",
        "group_order": 30,
        "source_order": 40,
        "cache_description": "新增100件馆藏",
        "visible": True,
    }
    with pytest.raises(FrozenInstanceError):
        value.short_label = "changed"


def test_registered_provider_display_contract(tmp_path):
    descriptors = build_services(
        tmp_path / "out", tmp_path / "cache"
    ).providers.descriptors()
    names = {}
    for descriptor in descriptors:
        presentation = descriptor.to_dict().get("presentation")
        assert presentation is not None, descriptor.id
        group = presentation["group_id"]
        identity = (presentation["group_label"], presentation["group_order"])
        assert names.setdefault(group, identity) == identity
        assert presentation["short_label"]
        assert presentation["detail_label"]
        assert presentation["visible"] == (descriptor.id != "xiaohongshu")
        if descriptor.capabilities.cache:
            assert presentation["cache_description"]


def test_frontend_descriptor_fixture_matches_backend(tmp_path):
    import json
    from pathlib import Path

    descriptors = build_services(
        tmp_path / "out", tmp_path / "cache"
    ).providers.descriptors()
    fixture = json.loads(
        Path("tests/fixtures/provider_descriptors.json").read_text("utf-8")
    )
    assert fixture == {
        descriptor.id: descriptor.to_dict() for descriptor in descriptors
    }
