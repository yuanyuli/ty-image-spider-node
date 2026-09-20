"""仅对同一素材串行化缓存写入，不阻塞其他素材的下载。"""

from contextlib import contextmanager
from threading import Lock
from typing import Iterator

from ..models import AssetItem


class AssetLocks:
    def __init__(self) -> None:
        self._guard = Lock()
        self._entries: dict[tuple[str, str, str], tuple[Lock, int]] = {}

    @contextmanager
    def hold(self, item: AssetItem) -> Iterator[None]:
        key = (item.provider, str(item.metadata.get("site") or ""), item.id)
        with self._guard:
            lock, users = self._entries.get(key, (Lock(), 0))
            self._entries[key] = (lock, users + 1)
        try:
            with lock:
                yield
        finally:
            with self._guard:
                lock, users = self._entries[key]
                if users == 1:
                    del self._entries[key]
                else:
                    self._entries[key] = (lock, users - 1)
