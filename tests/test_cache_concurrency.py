import threading
import time

import pytest

from ty_image_spider.models import SpiderError
from ty_image_spider.services.cache_job import CacheJobService


class BlockingRunner:
    def __init__(self):
        self.entered = {q: threading.Event() for q in ("one", "two", "three", "four")}
        self.release = threading.Event()

    def run(self, request, cancel, update):
        self.entered[request.query].set()
        while not self.release.wait(0.005):
            if cancel.is_set():
                break
        update(state="cancelled" if cancel.is_set() else "complete", cached=1)


def wait_terminal(service, job_id):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        value = service.status(job_id)
        if value["state"] != "running":
            return value
        time.sleep(0.005)
    pytest.fail("缓存任务未结束")


def test_jobs_deduplicate_limit_capacity_and_cancel_independently():
    runner = BlockingRunner()
    service = CacheJobService(runner, frozenset({"filmgrab"}))
    first = {"provider": "filmgrab", "query": " one ", "filters": {"b": 2, "a": 1}}
    jobs = []
    try:
        jobs.append(service.start(first))
        assert runner.entered["one"].wait(1)
        with pytest.raises(SpiderError) as duplicate:
            service.start({**first, "query": "one", "filters": {"a": 1, "b": 2}})
        assert duplicate.value.code == "cache_duplicate"
        assert duplicate.value.details["job_id"] == jobs[0]["id"]
        for query in ("two", "three"):
            jobs.append(service.start({"provider": "filmgrab", "query": query}))
            assert runner.entered[query].wait(1)
        with pytest.raises(SpiderError) as capacity:
            service.start({"provider": "filmgrab", "query": "four"})
        assert capacity.value.code == "cache_capacity"
        service.cancel(jobs[0]["id"])
        assert wait_terminal(service, jobs[0]["id"])["state"] == "cancelled"
        assert service.status(jobs[1]["id"])["state"] == "running"
        jobs.append(service.start({"provider": "filmgrab", "query": "four"}))
        assert runner.entered["four"].wait(1)
    finally:
        runner.release.set()
        for job in jobs:
            wait_terminal(service, job["id"])


def test_terminal_retention_prunes_by_age_and_count_but_never_running():
    runner = BlockingRunner()
    now = [100.0]
    service = CacheJobService(
        runner,
        frozenset({"filmgrab"}),
        max_history=2,
        retention_seconds=100,
        clock=lambda: now[0],
    )
    active = service.start({"provider": "filmgrab", "query": "one"})
    completed = []
    try:
        for _ in range(3):
            job = service.start({"provider": "filmgrab", "query": "two"})
            service.cancel(job["id"])
            completed.append(wait_terminal(service, job["id"]))
        with pytest.raises(SpiderError) as missing:
            service.status(completed[0]["id"])
        assert missing.value.status == 404
        now[0] = 201.0
        with pytest.raises(SpiderError):
            service.status(completed[-1]["id"])
        assert service.status(active["id"])["state"] == "running"
    finally:
        runner.release.set()
        wait_terminal(service, active["id"])


def test_thread_start_failure_releases_capacity(monkeypatch):
    runner = BlockingRunner()
    service = CacheJobService(runner, frozenset({"filmgrab"}), max_concurrency=1)
    original = threading.Thread.start

    def broken(self):
        raise RuntimeError("thread start failed")

    monkeypatch.setattr(threading.Thread, "start", broken)
    with pytest.raises(SpiderError) as error:
        service.start({"provider": "filmgrab", "query": "one"})
    assert error.value.code == "cache_start_failed"
    monkeypatch.setattr(threading.Thread, "start", original)
    runner.release.set()
    job = service.start({"provider": "filmgrab", "query": "one"})
    assert wait_terminal(service, job["id"])["state"] == "complete"


def test_cache_request_is_deeply_detached_and_canonical():
    from ty_image_spider.services.cache_request import CacheRequest

    filters = {"b": [1, {"a": 2}]}
    request = CacheRequest.from_payload(
        {"provider": "filmgrab", "query": " one ", "filters": filters}
    )
    key = request.fingerprint()
    filters["b"][1]["a"] = 3
    copy = request.to_payload()
    copy["filters"]["b"][1]["a"] = 4
    assert request.to_payload()["filters"] == {"b": [1, {"a": 2}]}
    assert request.fingerprint() == key
    assert request.query == "one"


@pytest.mark.parametrize("value", [float("nan"), object(), {1: "value"}])
def test_cache_request_rejects_non_json_filters(value):
    from ty_image_spider.services.cache_request import CacheRequest

    with pytest.raises(SpiderError):
        CacheRequest.from_payload({"provider": "filmgrab", "filters": {"key": value}})
