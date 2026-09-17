from ty_image_spider.services.opencli_connect import OpenCliConnectService
from ty_image_spider.models import SpiderError


class Runner:
    def __init__(self):
        self.calls = []

    def version(self):
        self.calls.append("version")
        return "1.8.8"

    def restart_daemon(self):
        self.calls.append("restart")

    def bridge_status(self):
        self.calls.append("bridge")

    def run_json(self, args, timeout_seconds):
        self.calls.append((args, timeout_seconds))
        return {"logged_in": True, "username": "测试用户"}


def test_connect_restarts_daemon_checks_bridge_and_login():
    runner = Runner()

    result = OpenCliConnectService(runner).execute()

    assert runner.calls == [
        "version",
        "restart",
        "bridge",
        (["xiaohongshu", "whoami", "--format", "json"], 30),
    ]
    assert result["connected"] is True
    assert "测试用户" in result["message"]


def test_connect_waits_for_extension_reconnection():
    runner = Runner()
    attempts = []

    def reconnecting():
        attempts.append(True)
        if len(attempts) < 3:
            raise SpiderError("opencli_bridge_unavailable", "扩展未连接", status=503)

    runner.bridge_status = reconnecting
    pauses = []
    result = OpenCliConnectService(runner, sleep=pauses.append).execute()
    assert result["connected"] is True
    assert len(attempts) == 3
    assert pauses == [1, 1]
