import subprocess

import pytest

from ty_image_spider.models import SpiderError
from ty_image_spider.opencli import CommandResult, OpenCliRunner


class FakeRun:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def __call__(self, args, **kwargs):
        self.calls.append((args, kwargs))
        if self.error:
            raise self.error
        return self.result


def completed(code=0, stdout="", stderr=""):
    return subprocess.CompletedProcess([], code, stdout, stderr)


def runner(fake_run, **kwargs):
    return OpenCliRunner(run=fake_run, which=lambda _: "C:/tools/opencli.cmd", **kwargs)


def test_runner_passes_arguments_without_shell_and_parses_json():
    fake_run = FakeRun(completed(0, '[{"title":"穿搭"}]'))

    rows = runner(fake_run).run_json(
        ["xiaohongshu", "search", "穿搭", "--format", "json"], 30
    )

    assert rows == [{"title": "穿搭"}]
    args, options = fake_run.calls[0]
    assert args == [
        "C:/tools/opencli.cmd",
        "xiaohongshu",
        "search",
        "穿搭",
        "--format",
        "json",
    ]
    assert options["shell"] is False
    assert options["timeout"] == 30


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (69, "opencli_bridge_unavailable"),
        (75, "opencli_timeout"),
        (77, "opencli_auth_required"),
        (78, "opencli_config_error"),
    ],
)
def test_runner_maps_documented_exit_codes(code, expected):
    fake_run = FakeRun(completed(code, '{"error":{"message":"failed"}}'))

    with pytest.raises(SpiderError) as caught:
        runner(fake_run).run_json(["doctor"], 5)

    assert caught.value.code == expected


def test_runner_reports_missing_executable_before_starting_process():
    fake_run = FakeRun(completed())
    opencli = OpenCliRunner(run=fake_run, which=lambda _: None)

    with pytest.raises(SpiderError) as caught:
        opencli.run_json(["doctor"], 5)

    assert caught.value.code == "opencli_missing"
    assert fake_run.calls == []


def test_runner_rejects_malformed_or_oversized_json_output():
    malformed = FakeRun(completed(0, "not-json"))
    with pytest.raises(SpiderError) as caught:
        runner(malformed).run_json(["doctor"], 5)
    assert caught.value.code == "opencli_invalid_json"

    oversized = FakeRun(completed(0, "[]   "))
    with pytest.raises(SpiderError) as caught:
        runner(oversized, max_stdout_bytes=4).run_json(["doctor"], 5)
    assert caught.value.code == "opencli_output_too_large"


def test_runner_maps_subprocess_timeout():
    fake_run = FakeRun(error=subprocess.TimeoutExpired(["opencli"], 3))

    with pytest.raises(SpiderError) as caught:
        runner(fake_run).run_json(["doctor"], 3)

    assert caught.value.code == "opencli_timeout"


def test_version_requires_supported_semantic_version():
    old = FakeRun(completed(0, "opencli 1.8.7\n"))
    with pytest.raises(SpiderError) as caught:
        runner(old).version()
    assert caught.value.code == "opencli_version_unsupported"

    current = FakeRun(completed(0, "1.8.8\n"))
    assert runner(current).version() == "1.8.8"


def test_doctor_returns_process_result():
    fake_run = FakeRun(completed(0, '{"ok":true}\n', ""))

    result = runner(fake_run).doctor()

    assert result == CommandResult(0, '{"ok":true}\n', "")
    assert fake_run.calls[0][0][-1:] == ["doctor"]


def test_doctor_maps_disconnected_extension_even_when_exit_code_is_zero():
    fake_run = FakeRun(
        completed(
            0,
            "[MISSING] Extension: not connected\n"
            "[FAIL] Connectivity: failed (Browser Bridge extension not connected)\n",
        )
    )

    with pytest.raises(SpiderError) as caught:
        runner(fake_run).doctor()

    assert caught.value.code == "opencli_bridge_unavailable"


def test_bridge_status_uses_fast_daemon_probe_and_maps_disconnection():
    fake_run = FakeRun(
        completed(0, "Daemon: running\nExtension: disconnected\nPort: 19825\n", "")
    )

    with pytest.raises(SpiderError) as caught:
        runner(fake_run).bridge_status()

    assert caught.value.code == "opencli_bridge_unavailable"
    assert fake_run.calls[0][0][-2:] == ["daemon", "status"]
    assert fake_run.calls[0][1]["timeout"] == 5


def test_bridge_status_accepts_connected_extension():
    fake_run = FakeRun(completed(0, "Daemon: running\nExtension: connected\n", ""))

    result = runner(fake_run).bridge_status()

    assert result.returncode == 0


def test_restart_daemon_uses_bounded_opencli_command():
    fake_run = FakeRun(completed(0, "Daemon restarted\n", ""))

    runner(fake_run).restart_daemon()

    assert fake_run.calls[0][0][-2:] == ["daemon", "restart"]
    assert fake_run.calls[0][1]["timeout"] == 15


def test_command_failure_preserves_xiaohongshu_filter_diagnostic():
    fake_run = FakeRun(
        completed(
            1,
            "ok: false\nerror:\n  message: filter layout (ambiguous_option)\n",
            "",
        )
    )

    with pytest.raises(SpiderError) as caught:
        runner(fake_run).run_json(["xiaohongshu", "search", "摄影"], 30)

    assert caught.value.code == "opencli_xiaohongshu_filter_changed"
    assert "筛选" in caught.value.message
