"""视频模块的目录职责和依赖方向测试。"""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
FORBIDDEN_BY_ROOT = {
    "src/ty_image_spider/domain": (
        "ty_image_spider.infrastructure",
        "ty_image_spider.providers",
        "folder_paths",
        "server",
    ),
    "src/ty_image_spider/infrastructure/video": (
        "ty_image_spider.providers",
        "ty_image_spider.api",
        "ty_image_spider.app",
    ),
    "src/ty_image_spider/providers/videos": (
        "ty_image_spider.api",
        "ty_image_spider.app",
        "folder_paths",
        "server",
    ),
}


def _imports(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return tuple(modules)


def test_video_directories_declare_their_boundaries():
    required = (
        ROOT / "docs/architecture/module-boundaries.md",
        ROOT / "src/ty_image_spider/infrastructure/video/__init__.py",
        ROOT / "src/ty_image_spider/providers/videos/__init__.py",
        ROOT / "src/ty_image_spider/providers/videos/shared/__init__.py",
        ROOT / "web/features/video/BOUNDARY.md",
    )

    assert all(path.is_file() for path in required)


def test_python_modules_follow_declared_dependency_direction():
    violations: list[str] = []
    for relative_root, forbidden in FORBIDDEN_BY_ROOT.items():
        root = ROOT / relative_root
        assert root.is_dir(), f"缺少边界目录: {relative_root}"
        for path in root.rglob("*.py"):
            for imported in _imports(path):
                if imported.startswith(forbidden):
                    violations.append(f"{path.relative_to(ROOT)} -> {imported}")

    assert violations == []


def test_concrete_video_sources_do_not_import_each_other():
    videos_root = ROOT / "src/ty_image_spider/providers/videos"
    source_names = {"prelinger", "commons", "nasa"}
    violations: list[str] = []
    for source_name in source_names:
        source_root = videos_root / source_name
        if not source_root.exists():
            continue
        forbidden = tuple(
            f"ty_image_spider.providers.videos.{name}"
            for name in source_names - {source_name}
        )
        for path in source_root.rglob("*.py"):
            for imported in _imports(path):
                if imported.startswith(forbidden):
                    violations.append(f"{path.relative_to(ROOT)} -> {imported}")

    assert violations == []
