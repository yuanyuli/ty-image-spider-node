"""后台缓存任务，仅负责遍历素材并写入持久索引。"""

from __future__ import annotations

import logging
import threading
import uuid
from typing import Mapping, Protocol

from ..asset_index import AssetIndex
from ..models import AssetDetail, SearchPage, SpiderError
from .cache_progress import CacheProgress


_LOGGER = logging.getLogger(__name__)


class SearchUseCase(Protocol):
    def execute(self, payload: Mapping[str, object]) -> SearchPage: ...


class DetailUseCase(Protocol):
    def execute(self, payload: Mapping[str, object]) -> AssetDetail: ...


class ImageReader(Protocol):
    def read(self, url: str, provider: str) -> tuple[bytes, str]: ...


class CacheJobService:
    def __init__(
        self,
        search: SearchUseCase,
        detail: DetailUseCase,
        index: AssetIndex,
        reader: ImageReader,
        enabled_providers: frozenset[str],
        progress: CacheProgress | None = None,
    ) -> None:
        self._search = search
        self._detail = detail
        self._index = index
        self._reader = reader
        self._enabled_providers = enabled_providers
        self._progress = progress
        self._lock = threading.Lock()
        self._cancel = threading.Event()
        self._job: dict[str, object] | None = None

    def start(self, payload: Mapping[str, object]) -> dict[str, object]:
        provider = payload.get("provider")
        query = payload.get("query", "")
        filters = payload.get("filters", {})
        if (
            not isinstance(provider, str)
            or provider not in self._enabled_providers
            or not isinstance(query, str)
            or not isinstance(filters, Mapping)
        ):
            raise SpiderError("invalid_cache_request", "当前素材源不支持批量缓存")
        if len(query) > 200:
            raise SpiderError("invalid_query", "搜索词过长")
        request = {"provider": provider, "query": query, "filters": dict(filters)}
        with self._lock:
            if self._job and self._job["state"] == "running":
                raise SpiderError("cache_busy", "已有缓存任务正在运行", status=409)
            self._cancel = threading.Event()
            self._job = {
                "id": uuid.uuid4().hex,
                "provider": provider,
                "state": "running",
                "cached": 0,
                "failed": 0,
                "skipped": 0,
                "target": 100,
                "message": "正在新增缓存，已有素材将跳过",
            }
            job_id = str(self._job["id"])
            thread = threading.Thread(
                target=self._run,
                args=(job_id, request, self._cancel),
                daemon=True,
                name="ty-image-spider-cache",
            )
            thread.start()
            return dict(self._job)

    def status(self, job_id: str) -> dict[str, object]:
        with self._lock:
            if self._job is None or self._job["id"] != job_id:
                raise SpiderError("cache_job_missing", "缓存任务不存在", status=404)
            return dict(self._job)

    def cancel(self, job_id: str) -> dict[str, object]:
        with self._lock:
            if self._job is None or self._job["id"] != job_id:
                raise SpiderError("cache_job_missing", "缓存任务不存在", status=404)
            if self._job["state"] == "running":
                self._cancel.set()
            return dict(self._job)

    def _update(self, job_id: str, **values: object) -> None:
        with self._lock:
            if self._job and self._job["id"] == job_id:
                self._job.update(values)

    def _run(
        self, job_id: str, request: dict[str, object], cancel: threading.Event
    ) -> None:
        seen: set[str] = set()
        cursors: set[str] = set()
        cursor: str | None = None
        cached = failed = skipped = 0
        exhausted = False
        try:
            cursor = self._progress.load(request) if self._progress else None
            while (
                cached < 100
                and len(seen) < 500
                and len(cursors) < 50
                and not cancel.is_set()
            ):
                if self._progress:
                    self._progress.save(request, cursor)
                page = self._search.execute({**request, "cursor": cursor})
                if page.choices:
                    raise SpiderError(
                        "movie_selection_required", "请先搜索并选择具体电影，再启动缓存"
                    )
                consumed = True
                for item in page.items:
                    if cancel.is_set() or cached >= 100 or len(seen) >= 500:
                        consumed = False
                        break
                    key = item.id
                    if key in seen:
                        continue
                    seen.add(key)
                    try:
                        if self._index.contains(item):
                            skipped += 1
                        else:
                            detail = self._detail.execute({"item": item.to_dict()})
                            url = detail.item.preview_url or item.preview_url
                            if not url:
                                raise SpiderError(
                                    "missing_preview", "素材没有可缓存的预览图"
                                )
                            image, extension = self._reader.read(url, item.provider)
                            if cancel.is_set():
                                consumed = False
                                break
                            self._index.store(detail, image, extension)
                            cached += 1
                    except Exception:
                        failed += 1
                        _LOGGER.warning(
                            "缓存素材失败: %s/%s", item.provider, item.id, exc_info=True
                        )
                    self._update(
                        job_id,
                        cached=cached,
                        failed=failed,
                        skipped=skipped,
                        message=f"新增 {cached}/100 张 · 跳过已有 {skipped} 张 · 失败 {failed} 张",
                    )
                if not consumed:
                    break
                if not page.next_cursor or page.next_cursor in cursors:
                    exhausted = not page.next_cursor
                    if exhausted and self._progress:
                        self._progress.clear(request)
                    break
                cursors.add(page.next_cursor)
                cursor = page.next_cursor
                if self._progress:
                    self._progress.save(request, cursor)
            state = "cancelled" if cancel.is_set() else "complete"
            prefix = "已取消" if state == "cancelled" else "缓存完成"
            suffix = (
                "；当前结果已读完"
                if exhausted
                else "；可再次点击继续"
                if cached < 100 and state == "complete"
                else ""
            )
            self._update(
                job_id,
                state=state,
                message=f"{prefix}：新增 {cached} 张，跳过已有 {skipped} 张，失败 {failed} 张{suffix}",
            )
        except SpiderError as exc:
            _LOGGER.warning("批量缓存任务失败 [%s]: %s", exc.code, exc.message)
            self._update(
                job_id,
                state="failed",
                code=exc.code,
                message=f"缓存中断：{exc.message}（本次新增 {cached} 张）",
            )
        except Exception as exc:
            _LOGGER.exception("批量缓存任务失败 [%s]: %s", type(exc).__name__, exc)
            self._update(
                job_id, state="failed", message="缓存任务中断，请查看 ComfyUI 日志"
            )
