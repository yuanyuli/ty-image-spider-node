"""资料缓存目录迁移不覆盖现有数据。"""

from ty_image_spider.infrastructure.cache_paths import prepare_cache_root


def test_existing_destination_preserves_both_directories(tmp_path):
    legacy = tmp_path / "ty-image-spider/.cache"
    target = tmp_path / "ty-node/ty-image-spider/.cache"
    legacy.mkdir(parents=True)
    target.mkdir(parents=True)
    (legacy / "mapping").write_bytes(b"old")
    (target / "mapping").write_bytes(b"new")

    assert prepare_cache_root(tmp_path) == target
    assert (target / "mapping").read_bytes() == b"new"
    assert (legacy / "mapping").read_bytes() == b"old"


def test_new_installation_does_not_create_legacy_directory(tmp_path):
    assert prepare_cache_root(tmp_path) == tmp_path / "ty-node/ty-image-spider/.cache"
    assert not (tmp_path / "ty-image-spider").exists()
