"""策展来源的受限图片下载。"""

from __future__ import annotations

from ..version import USER_AGENT

import os
import tempfile
from pathlib import Path
from http.client import HTTPException
from typing import Any, Callable
from urllib.error import URLError
from urllib.request import Request, urlopen

from PIL import Image

from ..models import DownloadResult, SpiderError
from ..security import read_limited, resolve_inside


from .download_policy import DownloadPolicy


class CuratedDownloader:
    def __init__(
        self, policy: DownloadPolicy, open_url: Callable[..., Any] = urlopen
    ) -> None:
        self._policy = policy
        self._open_url = open_url

    def read(self, url: str) -> tuple[bytes, str]:
        url = self._policy.normalize_url(url)
        request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "image/*"})
        try:
            with self._open_url(request, timeout=60) as response:
                self._policy.validate_url(response.geturl())
                payload = read_limited(response, 64 * 1024 * 1024)
        except SpiderError:
            raise
        except (URLError, TimeoutError, OSError, HTTPException) as exc:
            raise SpiderError("download_failed", "图片下载失败", status=502) from exc
        descriptor, name = tempfile.mkstemp(suffix=".image")
        path = Path(name)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
            with Image.open(path) as image:
                image.verify()
                extension = {
                    "JPEG": ".jpg",
                    "PNG": ".png",
                    "WEBP": ".webp",
                    "GIF": ".gif",
                }.get(image.format or "")
            if not extension:
                raise SpiderError(
                    "invalid_image", "远程内容不是受支持的图片", status=502
                )
            return payload, extension
        except (OSError, ValueError) as exc:
            raise SpiderError(
                "invalid_image", "远程内容不是有效图片", status=502
            ) from exc
        finally:
            path.unlink(missing_ok=True)

    def download(self, url: str, item_id: str, output_root: Path) -> DownloadResult:
        provider = self._policy.provider_id
        self._policy.validate_asset_id(item_id)
        self._policy.validate_url(url)
        directory = resolve_inside(output_root, Path("ty-image-spider") / provider)
        for suffix in (".jpg", ".png", ".webp", ".gif"):
            existing = resolve_inside(
                output_root, Path("ty-image-spider") / provider / f"{item_id}{suffix}"
            )
            if not existing.is_file():
                continue
            try:
                with Image.open(existing) as image:
                    image.load()
            except (OSError, ValueError, SyntaxError):
                continue
            return DownloadResult(
                (existing.relative_to(output_root.resolve()).as_posix(),),
                "图片已存在，已复用",
            )
        payload, extension = self.read(url)
        directory.mkdir(parents=True, exist_ok=True)
        target = resolve_inside(
            output_root, Path("ty-image-spider") / provider / f"{item_id}{extension}"
        )
        descriptor, name = tempfile.mkstemp(dir=directory, prefix=".image-")
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
            os.replace(name, target)
        finally:
            Path(name).unlink(missing_ok=True)
        return DownloadResult(
            (target.relative_to(output_root.resolve()).as_posix(),), "图片已下载"
        )
