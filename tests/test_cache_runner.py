import threading
from concurrent.futures import ThreadPoolExecutor

from ty_image_spider.asset_index import AssetIndex
from ty_image_spider.models import AssetDetail, AssetItem, SearchPage
from ty_image_spider.services.cache_request import CacheRequest
from ty_image_spider.services.cache_runner import CacheJobRunner


def test_cache_failure_log_omits_exception_payload(tmp_path, caplog):
    class Search:
        def execute(self, payload):
            raise RuntimeError("Bearer private-value")

    runner = CacheJobRunner(Search(), None, AssetIndex(tmp_path), None)
    result = {}
    runner.run(
        CacheRequest.from_payload({"provider": "filmgrab"}),
        threading.Event(),
        lambda **values: result.update(values),
    )
    assert result["state"] == "failed"
    assert "RuntimeError" in caplog.text
    assert "private-value" not in caplog.text


def test_concurrent_queries_count_shared_asset_only_once(tmp_path):
    entered = threading.Barrier(2)
    reading = threading.Event()
    release = threading.Event()
    calls = []

    class Search:
        def execute(self, payload):
            entered.wait(3)
            return SearchPage(
                (AssetItem("filmgrab", "1", preview_url="https://film-grab.com/a.jpg"),)
            )

    class Detail:
        def execute(self, payload):
            return AssetDetail(AssetItem.from_untrusted(payload["item"]))

    class Reader:
        def read(self, url, provider):
            calls.append(url)
            reading.set()
            assert release.wait(3)
            return b"test-image", ".jpg"

    runner = CacheJobRunner(Search(), Detail(), AssetIndex(tmp_path), Reader())

    def run(query):
        updates = {}
        runner.run(
            CacheRequest.from_payload({"provider": "filmgrab", "query": query}),
            threading.Event(),
            lambda **values: updates.update(values),
        )
        return updates

    with ThreadPoolExecutor(2) as executor:
        futures = [executor.submit(run, query) for query in ("one", "two")]
        assert reading.wait(3)
        release.set()
        results = [future.result(3) for future in futures]
    assert sum(result["cached"] for result in results) == 1
    assert sum(result["skipped"] for result in results) == 1
    assert len(calls) == 1
