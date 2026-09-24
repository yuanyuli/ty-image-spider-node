import threading
from concurrent.futures import ThreadPoolExecutor

from ty_image_spider.infrastructure.asset_index import AssetIndex
from ty_image_spider.infrastructure.video import VideoDownloader
from ty_image_spider.domain import AssetDetail, AssetItem, MediaResource, SearchPage
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


def test_video_cache_reads_only_static_poster_and_never_downloads_video(
    tmp_path, monkeypatch
):
    item = AssetItem(
        "prelinger",
        "movie-1",
        kind="video",
        preview_url="https://archive.org/services/img/movie-1",
    )
    media = MediaResource(
        "video",
        "https://archive.org/download/movie-1/movie-1.mp4",
        "video/mp4",
        "download",
    )
    reader_calls = []
    video_download_calls = []

    class Search:
        def execute(self, payload):
            return SearchPage((item,))

    class Detail:
        def execute(self, payload):
            return AssetDetail(item, (item.preview_url,), media=(media,))

    class Reader:
        def read(self, url, provider):
            reader_calls.append((url, provider))
            return b"poster", ".jpg"

    monkeypatch.setattr(
        VideoDownloader,
        "download",
        lambda self, *args: video_download_calls.append(args),
    )
    runner = CacheJobRunner(Search(), Detail(), AssetIndex(tmp_path), Reader())
    updates = {}

    runner.run(
        CacheRequest.from_payload({"provider": "prelinger"}),
        threading.Event(),
        lambda **values: updates.update(values),
    )

    assert reader_calls == [(item.preview_url, "prelinger")]
    assert video_download_calls == []
    assert updates["state"] == "complete"
