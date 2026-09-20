"""Civitai 图片的受限下载实现。"""

from __future__ import annotations

from .version import USER_AGENT

import os
import re
import tempfile
from pathlib import Path
from typing import Any, Callable
from urllib.request import Request, urlopen

from PIL import Image

from .models import DownloadResult, SpiderError
from .security import read_limited, require_https_host, resolve_inside


_MAX_IMAGE_BYTES = 64 * 1024 * 1024
_SAFE_ID = re.compile(r"^[0-9]+$")


def _is_civitai_host(host: str) -> bool:
    return (
        host in {"civitai.com", "civitai.red"}
        or host.endswith(".civitai.com")
        or host.endswith(".civitai.red")
    )


class ImageDownloader:
    def __init__(
        self,
        open_url: Callable[..., Any] = urlopen,
        *,
        max_bytes: int = _MAX_IMAGE_BYTES,
    ) -> None:
        self._open_url = open_url
        self._max_bytes = max_bytes

    def download(self, url: str, item_id: str, output_root: Path) -> DownloadResult:
        require_https_host(url, _is_civitai_host)
        if not _SAFE_ID.fullmatch(item_id):
            raise SpiderError("invalid_asset", "Civitai 素材 ID 无效")

        directory = resolve_inside(output_root, Path("ty-image-spider/civitai"))
        directory.mkdir(parents=True, exist_ok=True)
        request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "image/*"})
        try:
            with self._open_url(request, timeout=60) as response:
                try:
                    require_https_host(response.geturl(), _is_civitai_host)
                except SpiderError as exc:
                    raise SpiderError(
                        "unsafe_redirect", "图片下载发生了不安全的重定向"
                    ) from exc
                payload = read_limited(response, self._max_bytes)
        except SpiderError:
            raise
        except OSError as exc:
            raise SpiderError("download_failed", "图片下载失败", status=502) from exc

        descriptor, temp_name = tempfile.mkstemp(
            prefix=f".{item_id}-", suffix=".tmp", dir=directory
        )
        temp = Path(temp_name)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            extension = self._verify_image(temp)
            target = self._available_target(directory, item_id, extension)
            os.replace(temp, target)
        finally:
            temp.unlink(missing_ok=True)

        relative = target.relative_to(Path(output_root).resolve()).as_posix()
        return DownloadResult((relative,), "图片已下载")

    @staticmethod
    def _verify_image(path: Path) -> str:
        try:
            with Image.open(path) as image:
                image.verify()
                image_format = (image.format or "").lower()
        except (OSError, ValueError) as exc:
            raise SpiderError(
                "invalid_image", "下载内容不是有效图片", status=502
            ) from exc
        extensions = {"jpeg": ".jpg", "png": ".png", "webp": ".webp", "gif": ".gif"}
        extension = extensions.get(image_format)
        if extension is None:
            raise SpiderError("invalid_image", "下载内容不是支持的有效图片", status=502)
        return extension

    @staticmethod
    def _available_target(directory: Path, item_id: str, extension: str) -> Path:
        target = directory / f"{item_id}{extension}"
        if not target.exists():
            return target
        counter = 2
        while True:
            candidate = directory / f"{item_id}-{counter}{extension}"
            if not candidate.exists():
                return candidate
            counter += 1
