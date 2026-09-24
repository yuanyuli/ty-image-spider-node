"""受限、流式且原子落盘的视频下载器。"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, Callable
from urllib.request import Request, urlopen

from ...domain import DownloadResult, MediaResource, SpiderError
from ...version import USER_AGENT
from .files import find_valid_video
from .policy import VideoDownloadPolicy
from .signatures import detect_video_extension


class VideoDownloader:
    def __init__(
        self,
        policy: VideoDownloadPolicy,
        open_url: Callable[..., Any] = urlopen,
        *,
        chunk_size: int = 1024 * 1024,
    ) -> None:
        self._policy = policy
        self._open_url = open_url
        self._chunk_size = chunk_size

    def download(
        self, resource: MediaResource, item_id: str, output_root: Path
    ) -> DownloadResult:
        self._policy.require_item_id(item_id)
        self._policy.require_url(resource.url)
        root = Path(output_root).resolve()
        directory = root / "ty-image-spider" / self._policy.provider_id
        existing = find_valid_video(directory, item_id)
        if existing is not None:
            return self._result(existing, root, "视频已存在，已复用")

        directory.mkdir(parents=True, exist_ok=True)
        request = Request(
            resource.url,
            headers={"User-Agent": USER_AGENT, "Accept": "video/*"},
        )
        descriptor = -1
        temporary: Path | None = None
        try:
            with self._open_url(request, timeout=120) as response:
                try:
                    self._policy.require_url(response.geturl())
                except SpiderError as exc:
                    raise SpiderError(
                        "unsafe_redirect", "视频下载发生了不安全的重定向"
                    ) from exc
                self._require_declared_size(response.headers.get("Content-Length"))
                descriptor, temp_name = tempfile.mkstemp(
                    prefix=f".{item_id}-", suffix=".tmp", dir=directory
                )
                temporary = Path(temp_name)
                total = 0
                header = bytearray()
                with os.fdopen(descriptor, "wb") as handle:
                    descriptor = -1
                    while True:
                        chunk = response.read(self._chunk_size)
                        if not chunk:
                            break
                        total += len(chunk)
                        if total > self._policy.max_bytes:
                            raise SpiderError(
                                "video_too_large", "视频文件超过允许的大小"
                            )
                        if len(header) < 64:
                            header.extend(chunk[: 64 - len(header)])
                        handle.write(chunk)
                    handle.flush()
                    os.fsync(handle.fileno())
        except SpiderError:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
            raise
        except (OSError, TimeoutError) as exc:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
            raise SpiderError(
                "download_failed", "视频下载失败", status=502
            ) from exc
        finally:
            if descriptor >= 0:
                os.close(descriptor)

        assert temporary is not None
        try:
            extension = detect_video_extension(bytes(header))
            if extension is None:
                raise SpiderError(
                    "invalid_video", "下载内容不是支持的有效视频", status=502
                )
            target = directory / f"{item_id}{extension}"
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        return self._result(target, root, "视频已下载")

    def _require_declared_size(self, raw: object) -> None:
        if raw is None:
            return
        try:
            size = int(str(raw))
        except ValueError:
            return
        if size > self._policy.max_bytes:
            raise SpiderError("video_too_large", "视频文件超过允许的大小")

    @staticmethod
    def _result(path: Path, root: Path, message: str) -> DownloadResult:
        relative = path.relative_to(root).as_posix()
        return DownloadResult((relative,), message, str(root))
