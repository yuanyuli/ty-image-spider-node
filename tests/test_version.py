import json
import re
from pathlib import Path


def test_runtime_and_manifest_versions_match():
    from ty_image_spider.version import USER_AGENT, __version__

    assert __version__ == "2.5.0"
    assert USER_AGENT == "TY-Image-Spider/2.5.0"
    assert (
        re.search(
            r'^version = "([^"]+)"', Path("pyproject.toml").read_text("utf-8"), re.M
        )[1]
        == __version__
    )
    for file in ("package.json", "package-lock.json"):
        content = json.loads(Path(file).read_text("utf-8"))
        assert content["version"] == __version__
    assert content["packages"][""]["version"] == __version__


def test_no_stale_network_product_identifiers():
    for path in Path("src").rglob("*.py"):
        if path.name == "version.py":
            continue
        assert "TY-Image-Spider/" not in path.read_text("utf-8"), str(path)
