"""缓存任务协调器：仅管理去重、容量、取消与有限历史。"""

from __future__ import annotations
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Callable, Mapping, Protocol
from ..models import SpiderError
from .cache_request import CacheRequest

_LOGGER = logging.getLogger(__name__)


class CacheRunner(Protocol):
    def run(
        self,
        request: CacheRequest,
        cancel: threading.Event,
        update: Callable[..., None],
    ) -> None: ...


@dataclass
class CacheJobContext:
    request: CacheRequest
    status: dict[str, object]
    cancel: threading.Event = field(default_factory=threading.Event)
    finished_at: float = 0.0


class CacheJobService:
    def __init__(
        self,
        runner: CacheRunner,
        enabled_providers: frozenset[str],
        *,
        max_concurrency: int = 3,
        max_history: int = 64,
        retention_seconds: float = 86400,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if max_concurrency < 1 or max_history < 1 or retention_seconds <= 0:
            raise ValueError("缓存任务容量和保留期限必须为正数")
        self._runner = runner
        self._enabled_providers = enabled_providers
        self._max_history = max_history
        self._retention_seconds = retention_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._capacity = threading.BoundedSemaphore(max_concurrency)
        self._jobs: dict[str, CacheJobContext] = {}
        self._active_keys: dict[str, str] = {}

    def start(self, payload: Mapping[str, object]) -> dict[str, object]:
        request = CacheRequest.from_payload(payload)
        if request.provider not in self._enabled_providers:
            raise SpiderError("invalid_cache_request", "当前素材源不支持批量缓存")
        key = request.fingerprint()
        with self._lock:
            self._prune()
            existing = self._active_keys.get(key)
            if existing is not None:
                raise SpiderError(
                    "cache_duplicate",
                    "相同条件的缓存任务正在运行",
                    status=409,
                    details={"job_id": existing},
                )
            if not self._capacity.acquire(blocking=False):
                raise SpiderError(
                    "cache_capacity",
                    "同时运行的缓存任务已达上限，请等待任务完成",
                    status=409,
                )
            job_id = uuid.uuid4().hex
            now = self._clock()
            status: dict[str, object] = {
                "id": job_id,
                "provider": request.provider,
                "request_key": key,
                "created_at": now,
                "updated_at": now,
                "state": "running",
                "cached": 0,
                "failed": 0,
                "skipped": 0,
                "target": 100,
                "message": "正在新增缓存，已有素材将跳过",
            }
            context = CacheJobContext(request, status)
            self._jobs[job_id] = context
            self._active_keys[key] = job_id
            try:
                threading.Thread(
                    target=self._run,
                    args=(job_id, context),
                    daemon=True,
                    name=f"ty-image-spider-cache-{job_id[:8]}",
                ).start()
            except Exception as exc:
                del self._jobs[job_id]
                del self._active_keys[key]
                self._capacity.release()
                raise SpiderError(
                    "cache_start_failed", "无法启动缓存任务，请稍后重试", status=503
                ) from exc
            return dict(status)

    def status(self, job_id: str) -> dict[str, object]:
        with self._lock:
            return dict(self._get(job_id).status)

    def cancel(self, job_id: str) -> dict[str, object]:
        with self._lock:
            context = self._get(job_id)
            if context.status["state"] == "running":
                context.cancel.set()
            return dict(context.status)

    def _get(self, job_id: str) -> CacheJobContext:
        self._prune()
        context = self._jobs.get(job_id)
        if context is None:
            raise SpiderError(
                "cache_job_missing", "缓存任务不存在或已经过期", status=404
            )
        return context

    def _prune(self) -> None:
        now = self._clock()
        terminal = [
            (key, context.finished_at)
            for key, context in self._jobs.items()
            if context.status["state"] != "running"
        ]
        terminal.sort(key=lambda entry: entry[1])
        for position, (key, finished_at) in enumerate(terminal):
            if (
                now - finished_at >= self._retention_seconds
                or position < len(terminal) - self._max_history
            ):
                del self._jobs[key]

    def _run(self, job_id: str, context: CacheJobContext) -> None:
        terminal: dict[str, object] = {}

        def update(**values: object) -> None:
            # 终态与容量释放原子可见，防止界面已完成但重试仍判定重复。
            if values.get("state") in {"complete", "cancelled", "failed"}:
                terminal.update(values)
                return
            with self._lock:
                context.status.update(values, updated_at=self._clock())

        try:
            self._runner.run(context.request, context.cancel, update)
        except Exception:
            _LOGGER.error("缓存工作器异常退出：%s", job_id)
            terminal.update(state="failed", message="缓存任务中断，请查看 ComfyUI 日志")
        finally:
            with self._lock:
                context.status.update(terminal)
                if context.status["state"] == "running":
                    context.status.update(
                        state="failed", message="缓存工作器未返回完成状态"
                    )
                context.finished_at = self._clock()
                context.status["updated_at"] = context.finished_at
                self._active_keys.pop(context.request.fingerprint(), None)
                self._capacity.release()
                self._prune()
