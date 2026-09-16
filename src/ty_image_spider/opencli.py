"""OpenCLI 的安全进程调用边界。"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any, Callable, Sequence

from .models import SpiderError


_MINIMUM_VERSION = (1, 8, 8)
_VERSION_PATTERN = re.compile(r"(?<!\d)(\d+)\.(\d+)\.(\d+)(?!\d)")
_EXIT_CODES = {
    69: (
        "opencli_bridge_unavailable",
        "OpenCLI 浏览器桥接不可用",
        "请启动 Chrome 扩展后重试",
        503,
    ),
    75: ("opencli_timeout", "OpenCLI 执行超时", "请稍后重试", 504),
    77: (
        "opencli_auth_required",
        "小红书登录状态不可用",
        "请在 Chrome 中登录小红书",
        401,
    ),
    78: (
        "opencli_config_error",
        "OpenCLI 配置无效",
        "请运行 opencli doctor 检查配置",
        503,
    ),
}


@dataclass(frozen=True, slots=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


class OpenCliRunner:
    def __init__(
        self,
        executable: str = "opencli",
        *,
        run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
        which: Callable[[str], str | None] = shutil.which,
        max_stdout_bytes: int = 4 * 1024 * 1024,
    ) -> None:
        self._executable = executable
        self._run = run
        self._which = which
        self._max_stdout_bytes = max(1, max_stdout_bytes)

    def version(self) -> str:
        result = self._execute(["--version"], 10)
        match = _VERSION_PATTERN.search(result.stdout)
        if match is None:
            raise SpiderError(
                "opencli_version_invalid", "无法识别 OpenCLI 版本", status=503
            )
        version = tuple(int(part) for part in match.groups())
        if version < _MINIMUM_VERSION:
            raise SpiderError(
                "opencli_version_unsupported",
                f"OpenCLI 版本过低：{'.'.join(match.groups())}",
                "请升级到 OpenCLI 1.8.8 或更高版本",
                503,
            )
        return ".".join(match.groups())

    def doctor(self) -> CommandResult:
        result = self._execute(["doctor"], 30)
        report = f"{result.stdout}\n{result.stderr}".casefold()
        disconnected = (
            "extension: not connected" in report
            or "browser bridge extension not connected" in report
            or "connectivity: failed" in report
        )
        if disconnected:
            raise SpiderError(
                "opencli_bridge_unavailable",
                "OpenCLI Chrome 扩展未连接",
                "请启用 Chrome 扩展后重试",
                503,
            )
        return result

    def run_json(self, args: Sequence[str], timeout_seconds: int) -> Any:
        result = self._execute(args, timeout_seconds)
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise SpiderError(
                "opencli_invalid_json", "OpenCLI 返回的数据无法解析", status=502
            ) from exc

    def _execute(self, args: Sequence[str], timeout_seconds: int) -> CommandResult:
        executable = self._which(self._executable)
        if not executable:
            raise SpiderError(
                "opencli_missing",
                "未找到 OpenCLI",
                "请安装 OpenCLI 1.8.8 或更高版本",
                503,
            )
        arguments = self._validate_args(args)
        options: dict[str, Any] = {
            "shell": False,
            "capture_output": True,
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
            "timeout": max(1, int(timeout_seconds)),
        }
        if os.name == "nt":
            options["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            completed = self._run([executable, *arguments], **options)
        except subprocess.TimeoutExpired as exc:
            raise SpiderError(
                "opencli_timeout", "OpenCLI 执行超时", "请稍后重试", 504
            ) from exc
        except OSError as exc:
            raise SpiderError(
                "opencli_start_failed", "无法启动 OpenCLI", "请检查 OpenCLI 安装", 503
            ) from exc

        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        if len(stdout.encode("utf-8")) > self._max_stdout_bytes:
            raise SpiderError(
                "opencli_output_too_large", "OpenCLI 返回的数据超过大小限制", status=502
            )
        result = CommandResult(completed.returncode, stdout, stderr)
        if completed.returncode != 0:
            raise self._exit_error(completed.returncode)
        return result

    @staticmethod
    def _validate_args(args: Sequence[str]) -> list[str]:
        result: list[str] = []
        for value in args:
            if not isinstance(value, str) or "\0" in value:
                raise SpiderError("opencli_invalid_argument", "OpenCLI 参数无效")
            result.append(value)
        if not result:
            raise SpiderError("opencli_invalid_argument", "OpenCLI 命令不能为空")
        return result

    @staticmethod
    def _exit_error(returncode: int) -> SpiderError:
        mapped = _EXIT_CODES.get(returncode)
        if mapped is None:
            return SpiderError(
                "opencli_failed",
                f"OpenCLI 执行失败（退出码 {returncode}）",
                "请运行 opencli doctor 检查环境",
                502,
            )
        return SpiderError(*mapped)
