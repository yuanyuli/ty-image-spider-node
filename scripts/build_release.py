"""从指定 Git 提交生成可复现安装包；不读取工作区凭据或可变源码。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
import zipfile
from pathlib import Path, PurePosixPath


ROOT_FILES = frozenset(
    {
        "__init__.py",
        "LICENSE",
        "README.md",
        "CHANGELOG.md",
        "requirements.txt",
        "pyproject.toml",
        "tmdb.example.json",
        "CONTRIBUTING.md",
        "SECURITY.md",
        "CODE_OF_CONDUCT.md",
        "THIRD_PARTY_NOTICES.md",
    }
)
USER_DOCS = frozenset(
    {
        "docs/compatibility.md",
        "docs/source-rights.md",
        "docs/editorial-sources.md",
        "docs/curated-sources-cache.md",
        "docs/loc-source.md",
        "docs/museum-sources.md",
        "docs/nasa-source.md",
        "docs/tmdb-movie-mapping.md",
    }
)
FORBIDDEN_PARTS = frozenset(
    {
        ".local",
        ".env",
        "__pycache__",
        "node_modules",
        ".venv",
        "cache",
        "output",
        "dist",
    }
)
SECRET_NAME = re.compile(
    r"(?:^|/)(?:tmdb\.json|credentials(?:\.(?:json|ya?ml|toml|ini|txt))?|id_rsa|id_ed25519|[^/]+\.(?:pem|key|p12|pfx))$",
    re.I,
)
LOCAL_PATH = re.compile(r"(?<![\w])[A-Za-z]:[\\/]|/(?:Users|home)/[^\s/]+/")
CREDENTIAL = re.compile(
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|"
    r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})|"
    r"\beyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}|"
    r"""(?i:(?:api[_-]?key|read_access_token|access_token|secret)\s*["']?\s*[:=]\s*["'][A-Za-z0-9_./+-]{24,}["'])"""
)


def git(repo: Path, *args: str) -> bytes:
    return subprocess.check_output(
        ["git", "-C", str(repo), *args], stderr=subprocess.PIPE
    )


def included(name: str) -> bool:
    return (
        name in ROOT_FILES
        or name in USER_DOCS
        or (name.startswith("src/") and name.endswith(".py"))
        or (
            name.startswith("web/")
            and PurePosixPath(name).suffix in {".js", ".css", ".svg"}
        )
    )


def snapshot(repo: Path, ref: str) -> tuple[str, int, dict[str, bytes]]:
    revision = git(repo, "rev-parse", "--verify", f"{ref}^{{commit}}").decode().strip()
    entries = {}
    for record in git(repo, "ls-tree", "-rz", "--full-tree", revision).split(b"\0"):
        if not record:
            continue
        metadata, raw_name = record.split(b"\t", 1)
        mode, kind, oid = metadata.decode().split()
        name = raw_name.decode("utf-8")
        parts = PurePosixPath(name).parts
        if ".." in parts or name.startswith("/") or "\\" in name:
            raise ValueError("Git 路径不安全")
        # 只检查路径，不打开误跟踪的本地凭据。
        if set(p.lower() for p in parts) & FORBIDDEN_PARTS or SECRET_NAME.search(name):
            raise ValueError("Git 跟踪了禁止分发的路径，请从版本控制移除")
        if included(name) or name in {"package.json", "package-lock.json"}:
            if mode not in {"100644", "100755"} or kind != "blob":
                raise ValueError("安装包不接受符号链接或子模块")
            entries[name] = git(repo, "cat-file", "blob", oid)
    if not ROOT_FILES <= entries.keys():
        raise ValueError("缺少安装包必需文件")
    version_file = entries.get("src/ty_image_spider/version.py", b"").decode()
    match = re.search(r'^__version__\s*=\s*"(\d+\.\d+\.\d+)"', version_file, re.M)
    project = re.search(
        r'^version\s*=\s*"([^"]+)"', entries["pyproject.toml"].decode(), re.M
    )
    if not match or not project:
        raise ValueError("缺少有效版本")
    version = match[1]
    try:
        package = json.loads(entries["package.json"])
        lock = json.loads(entries["package-lock.json"])
        versions = [
            project[1],
            package["version"],
            lock["version"],
            lock["packages"][""]["version"],
        ]
    except (KeyError, ValueError) as exc:
        raise ValueError("包版本信息不完整") from exc
    if any(v != version for v in versions):
        raise ValueError("Python、npm 与运行时版本不一致")
    files = {name: data for name, data in entries.items() if included(name)}
    for name, data in files.items():
        text = data.decode("utf-8")
        if LOCAL_PATH.search(text) or CREDENTIAL.search(text):
            raise ValueError(
                f"文件存在本机绝对路径或疑似凭据：{name}（不输出匹配内容）"
            )
    epoch = int(
        os.environ.get("SOURCE_DATE_EPOCH")
        or git(repo, "show", "-s", "--format=%ct", revision)
    )
    if not 315532800 <= epoch <= 4354819199:
        raise ValueError("归档时间必须在 ZIP 支持的 1980–2107 年范围内")
    return version, epoch, files


def build_release(
    repo: Path, output: Path, *, ref: str = "HEAD", check: bool = False
) -> Path | None:
    version, epoch, files = snapshot(repo, ref)
    if check:
        return None
    output.mkdir(parents=True, exist_ok=True)
    archive = output / f"ty-image-spider-node-{version}.zip"
    checksum = archive.with_suffix(".zip.sha256")
    temporary: list[Path] = []
    try:

        def temp_path() -> Path:
            descriptor, name = tempfile.mkstemp(dir=output, suffix=".tmp")
            os.close(descriptor)
            path = Path(name)
            temporary.append(path)
            return path

        package_path, hash_path = temp_path(), temp_path()
        # STORE 避免各系统 zlib 版本导致相同快照的压缩字节不同。
        with zipfile.ZipFile(
            package_path, "w", compression=zipfile.ZIP_STORED
        ) as stream:
            for name in sorted(files):
                info = zipfile.ZipInfo(
                    "ty-image-spider-node/" + name, time.gmtime(epoch)[:6]
                )
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                stream.writestr(info, files[name])
        digest = hashlib.sha256(package_path.read_bytes()).hexdigest()
        hash_path.write_text(
            f"{digest}  {archive.name}\n", encoding="utf-8", newline="\n"
        )
        os.replace(package_path, archive)
        os.replace(hash_path, checksum)
        return archive
    finally:
        for path in temporary:
            path.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref", default="HEAD", help="目标 Git 提交或标签，默认 HEAD")
    parser.add_argument("--output", type=Path, default=Path("dist"))
    parser.add_argument(
        "--check", action="store_true", help="仅验证提交快照，不生成安装包"
    )
    args = parser.parse_args()
    try:
        path = build_release(
            Path(__file__).resolve().parents[1],
            args.output,
            ref=args.ref,
            check=args.check,
        )
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        parser.exit(
            1,
            f"发布检查失败：{type(exc).__name__}；{exc if isinstance(exc, ValueError) else '请检查 Git 和输出目录'}\n",
        )
    print(f"已生成：{path}" if path else "发布快照检查通过")


if __name__ == "__main__":
    main()
