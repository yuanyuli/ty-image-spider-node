"""OpenCLI 一键连接用例。"""

from __future__ import annotations

import time
import threading
from typing import Callable, Mapping

from ..models import SpiderError
from ..opencli import OpenCliRunner


class OpenCliConnectService:
    def __init__(
        self,
        runner: OpenCliRunner,
        *,
        sleep: Callable[[float], None] = time.sleep,
        session_lock: threading.Lock | None = None,
    ) -> None:
        self._runner = runner
        self._sleep = sleep
        self._lock = session_lock or threading.Lock()

    def execute(self) -> dict[str, object]:
        with self._lock:
            return self._connect()

    def _connect(self) -> dict[str, object]:
        version = self._runner.version()
        self._runner.restart_daemon()
        for attempt in range(10):
            try:
                self._runner.bridge_status()
                break
            except SpiderError as exc:
                if exc.code != "opencli_bridge_unavailable" or attempt == 9:
                    raise
                self._sleep(1)
        account = self._runner.run_json(
            ["xiaohongshu", "whoami", "--format", "json"], 30
        )
        if not isinstance(account, Mapping) or account.get("logged_in") is not True:
            raise SpiderError(
                "opencli_auth_required",
                "Chrome 中的小红书尚未登录",
                "请在 Chrome 登录小红书后重试",
                401,
            )
        username = account.get("username")
        suffix = f"，账号：{username}" if isinstance(username, str) and username else ""
        return {
            "connected": True,
            "version": version,
            "steps": [
                "OpenCLI 版本已确认",
                "守护进程已重启",
                "Chrome 扩展已连接",
                "小红书登录已确认",
            ],
            "message": f"OpenCLI 已连接{suffix}",
        }
