"""从 Git 快照分发，防止工作区漂移与敏感文件进入安装包。"""

import hashlib
import importlib.util
import json
import subprocess
import zipfile
from pathlib import Path

import pytest


@pytest.fixture
def release_module():
    spec = importlib.util.spec_from_file_location(
        "release", Path(__file__).resolve().parents[1] / "scripts/build_release.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args])


def commit(repo):
    git(repo, "add", ".")
    git(
        repo,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "-qm",
        "测试快照",
    )


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q")
    files = {
        "__init__.py": "# 节点入口\n",
        "src/ty_image_spider/version.py": '__version__ = "2.5.0"\n',
        "web/app.js": "// 界面\n",
        "pyproject.toml": '[project]\nversion = "2.5.0"\n',
        "package.json": json.dumps({"version": "2.5.0"}),
        "package-lock.json": json.dumps(
            {"version": "2.5.0", "packages": {"": {"version": "2.5.0"}}}
        ),
        "LICENSE": "MIT License\n",
        "README.md": "# 安装\n",
        "CHANGELOG.md": "# 更新\n",
        "requirements.txt": "Pillow>=10\n",
        "tmdb.example.json": '{"read_access_token": ""}\n',
        "CONTRIBUTING.md": "# 贡献\n",
        "SECURITY.md": "# 安全\n",
        "CODE_OF_CONDUCT.md": "# 行为\n",
        "THIRD_PARTY_NOTICES.md": "# 第三方\n",
        "docs/compatibility.md": "# 兼容性\n",
        "tests/private.py": "development only",
        "docs/superpowers/plan.md": "development only",
        "scripts/dev.py": "development only",
    }
    for name, value in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="utf-8")
    commit(root)
    return root


def test_release_uses_commit_bytes_and_repeats_exactly(release_module, repo, tmp_path):
    first = release_module.build_release(repo, tmp_path / "one")
    (repo / "README.md").write_text("uncommitted", encoding="utf-8")
    second = release_module.build_release(repo, tmp_path / "two")
    assert first.read_bytes() == second.read_bytes()
    with zipfile.ZipFile(first) as archive:
        names = archive.namelist()
        assert names == sorted(names)
        assert all(n.startswith("ty-image-spider-node/") for n in names)
        assert not any(
            p in n
            for n in names
            for p in ("tests/", "scripts/", "superpowers/", "package.json")
        )
        assert archive.read("ty-image-spider-node/README.md").decode() == "# 安装\n"
        assert len({i.date_time for i in archive.infolist()}) == 1
    assert (
        hashlib.sha256(first.read_bytes()).hexdigest()
        in first.with_suffix(".zip.sha256").read_text()
    )


@pytest.mark.parametrize(
    "name,value",
    [
        (".local/tmdb.json", "do not read"),
        ("web/private-key.pem", "private"),
        ("README.md", "C:\\Users\\someone\\project"),
        (
            "README.md",
            "Bearer eyJhbGciOiJIUzI1NiJ9.abcdefghijklmnopqrstuv.abcdefghijklmnopqrstuv",
        ),
        ("src/token.py", 'API_KEY = "abcdefghijklmnopqrstuvwxyz123456"'),
        ("package.json", '{"version": "9.0.0"}'),
    ],
)
def test_rejects_unsafe_or_inconsistent_snapshot(
    release_module, repo, tmp_path, name, value
):
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")
    commit(repo)
    with pytest.raises(ValueError):
        release_module.build_release(repo, tmp_path / "out")
    assert not list((tmp_path / "out").glob("*"))


def test_check_does_not_write_archive(release_module, repo, tmp_path):
    assert release_module.build_release(repo, tmp_path / "out", check=True) is None
    assert not (tmp_path / "out").exists()
