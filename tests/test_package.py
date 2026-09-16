from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).parents[1]


def load_root_package():
    spec = importlib.util.spec_from_file_location(
        "ty_image_spider_comfy_package",
        ROOT / "__init__.py",
        submodule_search_locations=[str(ROOT)],
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_package_registers_only_new_node_id():
    package = load_root_package()

    assert set(package.NODE_CLASS_MAPPINGS) == {"TyImageSpider"}
    assert package.NODE_DISPLAY_NAME_MAPPINGS == {
        "TyImageSpider": "TY Image Spider · 素材浏览"
    }
    assert package.WEB_DIRECTORY == "./web"

