import time
import threading

import pytest

from ty_image_spider.asset_index import AssetIndex
from ty_image_spider.models import AssetDetail, AssetItem, SearchPage, SpiderError
from ty_image_spider.services.cache_job import CacheJobService
from ty_image_spider.services.cache_runner import CacheJobRunner
from ty_image_spider.services.cache_progress import CacheProgress
from ty_image_spider.cache import JsonCache


class SearchStub:
    def execute(self, payload):
        page = int(payload.get("cursor") or "1")
        return SearchPage(
            (
                AssetItem(
                    "filmgrab",
                    f"{page}-1",
                    preview_url="https://film-grab.com/preview.jpg",
                ),
            ),
            str(page + 1) if page < 3 else None,
        )


class DetailStub:
    def execute(self, payload):
        return AssetDetail(AssetItem.from_untrusted(payload["item"]))


class ImageStub:
    def read(self, url, provider):
        assert provider == "filmgrab"
        return b"image", ".jpg"


def test_cache_job_walks_pages_and_indexes_distinct_items(tmp_path):
    index = AssetIndex(tmp_path)
    service = cache_service(
        SearchStub(), DetailStub(), index, ImageStub(), frozenset({"filmgrab"})
    )
    started = service.start({"provider": "filmgrab", "query": "film", "filters": {}})
    status = finished(service, started["id"])
    assert status["state"] == "complete"
    assert status["cached"] == 3
    assert index.overlay(AssetItem("filmgrab", "2-1")).preview_url.startswith("/view?")


def finished(service, job_id):
    # 这里验证真实磁盘写入结果，不约束共享 CI runner 的 I/O 性能。
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        status = service.status(job_id)
        if status["state"] != "running":
            return status
        time.sleep(0.02)
    pytest.fail(f"缓存任务未及时结束：{service.status(job_id)}")


def test_cache_job_stops_at_100_and_second_run_reuses_index(tmp_path):
    class Many(SearchStub):
        def execute(self, payload):
            return SearchPage(
                tuple(
                    AssetItem(
                        "filmgrab",
                        f"{i}-1",
                        preview_url="https://film-grab.com/image.jpg",
                    )
                    for i in range(150)
                )
            )

    class Counter(ImageStub):
        calls = 0

        def read(self, url, provider):
            self.calls += 1
            return super().read(url, provider)

    reader = Counter()
    service = cache_service(
        Many(), DetailStub(), AssetIndex(tmp_path), reader, frozenset({"filmgrab"})
    )
    assert (
        finished(service, service.start({"provider": "filmgrab"})["id"])["cached"]
        == 100
    )
    second = finished(service, service.start({"provider": "filmgrab"})["id"])
    assert second["cached"] == 50
    assert second["skipped"] == 100
    assert reader.calls == 150
    third = finished(service, service.start({"provider": "filmgrab"})["id"])
    assert third["cached"] == 0
    assert third["skipped"] == 150
    assert reader.calls == 150


def test_cache_job_rejects_concurrency_and_honors_cancel(tmp_path):
    entered, release = threading.Event(), threading.Event()

    class Blocking(SearchStub):
        def execute(self, payload):
            entered.set()
            release.wait(2)
            return super().execute(payload)

    service = cache_service(
        Blocking(),
        DetailStub(),
        AssetIndex(tmp_path),
        ImageStub(),
        frozenset({"filmgrab"}),
    )
    job_id = service.start({"provider": "filmgrab"})["id"]
    assert entered.wait(1)
    try:
        with pytest.raises(SpiderError, match="正在运行"):
            service.start({"provider": "filmgrab"})
        service.cancel(job_id)
    finally:
        release.set()
    status = finished(service, job_id)
    assert status["state"] == "cancelled"
    assert status["cached"] == 0


def test_cache_job_rejects_bad_provider_shape(tmp_path):
    service = cache_service(
        SearchStub(),
        DetailStub(),
        AssetIndex(tmp_path),
        ImageStub(),
        frozenset({"filmgrab"}),
    )
    with pytest.raises(SpiderError):
        service.start({"provider": []})


def test_cache_job_continues_past_empty_pages_with_next_cursor(tmp_path):
    class EmptyFirst(SearchStub):
        def execute(self, payload):
            if payload.get("cursor") is None:
                return SearchPage((), "2")
            return super().execute(payload)

    service = cache_service(
        EmptyFirst(),
        DetailStub(),
        AssetIndex(tmp_path),
        ImageStub(),
        frozenset({"filmgrab"}),
    )
    result = finished(service, service.start({"provider": "filmgrab"})["id"])
    assert result["cached"] == 2


def test_cache_job_reports_source_error_and_preserves_completed_count(tmp_path):
    class Unavailable(SearchStub):
        def execute(self, payload):
            if payload.get("cursor"):
                raise SpiderError("filmgrab_unavailable", "FilmGrab 暂时无法访问")
            return super().execute(payload)

    service = cache_service(
        Unavailable(),
        DetailStub(),
        AssetIndex(tmp_path),
        ImageStub(),
        frozenset({"filmgrab"}),
    )
    result = finished(service, service.start({"provider": "filmgrab"})["id"])
    assert result["state"] == "failed"
    assert result["cached"] == 1
    assert result["code"] == "filmgrab_unavailable"
    assert "FilmGrab 暂时无法访问" in result["message"]


def test_cache_continuation_survives_restart_and_isolates_queries(tmp_path):
    calls = []

    class Pages:
        def execute(self, payload):
            page = int(payload.get("cursor") or "1")
            calls.append((payload.get("query"), page))
            return SearchPage(
                tuple(
                    AssetItem(
                        "filmgrab",
                        f"{page}-{i}",
                        preview_url="https://film-grab.com/preview.jpg",
                    )
                    for i in range(60)
                ),
                str(page + 1),
            )

    def service():
        return cache_service(
            Pages(),
            DetailStub(),
            AssetIndex(tmp_path),
            ImageStub(),
            frozenset({"filmgrab"}),
            CacheProgress(JsonCache(tmp_path / "progress")),
        )

    first_service = service()
    first = finished(
        first_service,
        first_service.start({"provider": "filmgrab", "query": "one"})["id"],
    )
    assert first["cached"] == 100
    calls.clear()
    restarted = service()
    second = finished(
        restarted, restarted.start({"provider": "filmgrab", "query": "one"})["id"]
    )
    assert calls[0] == ("one", 2)
    assert second["cached"] == 100
    assert second["skipped"] == 40
    calls.clear()
    finished(restarted, restarted.start({"provider": "filmgrab", "query": "two"})["id"])
    assert calls[0] == ("two", 1)


def cache_service(search, detail, index, reader, enabled_providers, progress=None):
    return CacheJobService(
        CacheJobRunner(search, detail, index, reader, progress), enabled_providers
    )
