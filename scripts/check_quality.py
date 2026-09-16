"""运行节点发布前的完整质量门禁。"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def run(label: str, command: list[str]) -> None:
    print(f"\n[检查] {label}", flush=True)
    completed = subprocess.run(command, cwd=ROOT, check=False)
    if completed.returncode:
        raise SystemExit(completed.returncode)


def executable(name: str) -> str:
    value = shutil.which(name)
    if not value:
        print(f"缺少质量检查工具：{name}", file=sys.stderr)
        raise SystemExit(2)
    return value


def main() -> None:
    python_targets = ["src", "tests", "scripts"]
    mypy_targets = [
        "src/ty_image_spider/models.py",
        "src/ty_image_spider/cache.py",
        "src/ty_image_spider/security.py",
        "src/ty_image_spider/metadata.py",
        "src/ty_image_spider/downloads.py",
        "src/ty_image_spider/opencli.py",
        "src/ty_image_spider/providers",
        "src/ty_image_spider/services",
    ]
    node = executable("node")
    npx = executable("npx")
    js_tests = sorted(
        str(path.relative_to(ROOT)) for path in (ROOT / "tests").glob("*.test.mjs")
    )
    js_modules = sorted(
        str(path.relative_to(ROOT)) for path in (ROOT / "web").glob("*.js")
    )

    run("Ruff 规则", [PYTHON, "-m", "ruff", "check", *python_targets])
    run("Ruff 格式", [PYTHON, "-m", "ruff", "format", "--check", *python_targets])
    run(
        "Mypy 类型",
        [
            PYTHON,
            "-m",
            "mypy",
            "--explicit-package-bases",
            "--follow-imports=skip",
            *mypy_targets,
        ],
    )
    run("Python 测试", [PYTHON, "-m", "pytest", "-q"])
    run("前端测试", [node, "--test", *js_tests])
    run("Prettier", [npx, "--no-install", "prettier", "--check", "web", *js_tests])
    for module in js_modules:
        run(f"JS 语法：{module}", [node, "--check", module])
    run("Python 字节码", [PYTHON, "-m", "compileall", "-q", "src"])
    run("未暂存差异", [executable("git"), "diff", "--check"])
    run("已暂存差异", [executable("git"), "diff", "--cached", "--check"])
    print("\n全部质量检查通过。", flush=True)


if __name__ == "__main__":
    main()
