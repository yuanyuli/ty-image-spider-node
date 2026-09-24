"""仓库目录与文档链接契约。"""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_repository_uses_organized_development_paths():
    for path in (
        "scripts/quality/check.py",
        "scripts/quality/check_js.mjs",
        "scripts/quality/test_frontend.mjs",
        "scripts/release/build.py",
        "docs/guides/compatibility.md",
        "docs/sources/museum.md",
    ):
        assert (ROOT / path).is_file(), path


def test_relative_markdown_links_resolve():
    missing: list[str] = []
    for document in ROOT.rglob("*.md"):
        if any(
            part in {"node_modules", ".artifacts", ".git"} for part in document.parts
        ):
            continue
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", document.read_text("utf-8")):
            target = target.strip().split("#", 1)[0]
            if not target or "://" in target or target.startswith(("mailto:", "#")):
                continue
            if not (document.parent / target).resolve().exists():
                missing.append(f"{document.relative_to(ROOT)} -> {target}")
    assert not missing, "\n".join(missing)
