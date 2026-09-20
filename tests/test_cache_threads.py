from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

from ty_image_spider.cache import JsonCache
from ty_image_spider.services.cache_progress import CacheProgress


def test_prune_tolerates_file_disappearing_after_listing(tmp_path, monkeypatch):
    cache = JsonCache(tmp_path, max_entries=2)
    cache.put("old", 1)
    old = cache._path("old")
    original = Path.stat

    def disappear(path, *args, **kwargs):
        if path == old:
            path.unlink(missing_ok=True)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", disappear)
    cache.put("new", 2)
    assert cache.get("new", None) == 2


def test_three_tasks_share_progress_cache_while_pruning(tmp_path):
    cache = JsonCache(tmp_path, max_entries=20)
    progress = CacheProgress(cache)
    for i in range(20):
        cache.put(str(i), i)
    finished = Barrier(3)

    def worker(index):
        for i in range(50):
            request = {"provider": "nasa", "query": f"{index}-{i}"}
            progress.save(request, str(i))
            progress.load(request)
        finished.wait(5)
        request = {"provider": "nasa", "query": f"final-{index}"}
        progress.save(request, "done")
        return request

    with ThreadPoolExecutor(3) as pool:
        requests = list(pool.map(worker, range(3)))
    assert len(list(tmp_path.glob("*.json"))) <= 20
    assert all(progress.load(request) == "done" for request in requests)
