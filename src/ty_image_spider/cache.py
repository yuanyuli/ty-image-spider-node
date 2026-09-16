"""小型原子 JSON 缓存。"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any


class JsonCache:
    def __init__(self, root: Path, max_entries: int = 200):
        self.root = Path(root)
        self.max_entries = max(1, int(max_entries))
        self.root.mkdir(parents=True, exist_ok=True)

    def _now(self) -> float:
        return time.time()

    def _path(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self.root / f"{digest}.json"

    def get(self, key: str, max_age_seconds: float | None) -> Any | None:
        path = self._path(key)
        if not path.is_file():
            return None
        if max_age_seconds is not None and self._now() - path.stat().st_mtime > max_age_seconds:
            path.unlink(missing_ok=True)
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            path.unlink(missing_ok=True)
            return None

    def put(self, key: str, value: Any) -> None:
        target = self._path(key)
        descriptor, temporary_name = tempfile.mkstemp(prefix=".cache-", dir=self.root)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(value, handle, ensure_ascii=False, separators=(",", ":"))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, target)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)
        self._prune(protected=target)

    def clear(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def _prune(self, protected: Path) -> None:
        files = sorted(
            (path for path in self.root.glob("*.json") if path != protected),
            key=lambda path: path.stat().st_mtime_ns,
            reverse=True,
        )
        for path in files[max(0, self.max_entries - 1) :]:
            path.unlink(missing_ok=True)
