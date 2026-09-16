import json
import os
import time
from pathlib import Path

from ty_image_spider.cache import JsonCache


def test_cache_uses_atomic_hashed_paths_and_expires(tmp_path, monkeypatch):
    cache = JsonCache(tmp_path, max_entries=2)
    cache.put("secret?xsec_token=abc", {"value": 1})
    files = list(tmp_path.glob("*.json"))

    assert len(files) == 1
    assert "secret" not in files[0].name
    monkeypatch.setattr(cache, "_now", lambda: files[0].stat().st_mtime + 11)
    assert cache.get("secret?xsec_token=abc", max_age_seconds=10) is None
    assert not files[0].exists()


def test_cache_prunes_old_entries_and_removes_corrupt_json(tmp_path):
    cache = JsonCache(tmp_path, max_entries=2)
    for index in range(3):
        cache.put(str(index), {"index": index})
        path = next(path for path in tmp_path.glob("*.json") if json.loads(path.read_text())["index"] == index)
        path.touch()

    assert len(list(tmp_path.glob("*.json"))) == 2
    cache.put("broken", {"value": "will-break"})
    corrupt = next(path for path in tmp_path.glob("*.json") if "will-break" in path.read_text())
    corrupt.write_text("{", encoding="utf-8")
    assert cache.get("broken", 60) is None
    assert not corrupt.exists()


def test_cache_clear_removes_only_selected_key(tmp_path):
    cache = JsonCache(tmp_path)
    cache.put("a", {"value": "a"})
    cache.put("b", {"value": "b"})
    cache.clear("a")

    assert cache.get("a", 60) is None
    assert cache.get("b", 60) == {"value": "b"}


def test_pruning_never_removes_the_entry_just_written(tmp_path):
    cache = JsonCache(tmp_path, max_entries=2)
    cache.put("old-a", {"value": "a"})
    cache.put("old-b", {"value": "b"})
    future = time.time() + 60
    for path in tmp_path.glob("*.json"):
        os.utime(path, (future, future))

    cache.put("new", {"value": "new"})

    assert cache.get("new", None) == {"value": "new"}
    assert len(list(tmp_path.glob("*.json"))) == 2
