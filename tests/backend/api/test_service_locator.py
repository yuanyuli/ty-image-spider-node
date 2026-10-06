"""服务定位器使用 ComfyUI 输出目录，且保留旧缓存数据。"""

import sys
from types import SimpleNamespace

from ty_image_spider.api import service_locator


def test_services_move_existing_cache_under_ty_node(tmp_path, monkeypatch):
    legacy = tmp_path / "ty-image-spider" / ".cache"
    legacy.mkdir(parents=True)
    (legacy / "mapping.txt").write_text("电影映射", encoding="utf-8")
    calls = []
    service = object()
    monkeypatch.setitem(
        sys.modules,
        "folder_paths",
        SimpleNamespace(get_output_directory=lambda: str(tmp_path)),
    )
    monkeypatch.setattr(service_locator, "_services", None)

    def build(output, cache):
        calls.append((output, cache))
        assert (cache / "mapping.txt").read_text("utf-8") == "电影映射"
        return service

    monkeypatch.setattr(service_locator, "build_services", build)

    assert service_locator.get_services() is service
    assert service_locator.get_services() is service
    assert calls == [(tmp_path, tmp_path / "ty-node/ty-image-spider/.cache")]
    assert not legacy.exists()
