"""策展来源的受限图片下载。"""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from http.client import HTTPException
from typing import Any, Callable
from urllib.error import URLError
from urllib.parse import quote, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from PIL import Image

from ..models import DownloadResult, SpiderError
from ..security import read_limited, require_https_host, resolve_inside


_HOSTS = {
    "behance": lambda host: host.endswith(".behance.net") and host.startswith("mir-"),
    "filmgrab": lambda host: host == "film-grab.com",
    "civitai": lambda host: (
        host in {"civitai.com", "civitai.red"}
        or host.endswith(".civitai.com")
        or host.endswith(".civitai.red")
    ),
    "wallhaven": lambda host: host in {"th.wallhaven.cc", "w.wallhaven.cc"},
    "artic": lambda host: host == "www.artic.edu",
    "vam": lambda host: host == "framemark.vam.ac.uk",
    "cleveland": lambda host: host == "openaccess-cdn.clevelandart.org",
    "colossal": lambda host: host in {"www.thisiscolossal.com", "thisiscolossal.com"},
    "designmilk": lambda host: host == "design-milk.com",
    "featureshoot": lambda host: host in {"www.featureshoot.com", "i0.wp.com"},
    "mymodernmet": lambda host: host == "mymodernmet.com",
    "aperture": lambda host: host == "aperture.org",
    "printmag": lambda host: host == "www.printmag.com",
    "nasa": lambda host: host == "images-assets.nasa.gov",
    "loc": lambda host: host == "tile.loc.gov",
    "arena": lambda host: host in {"images.are.na", "d2w9rnfcy7mm78.cloudfront.net"},
}
_SAFE_ID = re.compile(r"^[0-9]+(?:-[0-9]+)?$")
_SAFE_LOC_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def validate_asset_id(provider: str, item_id: str) -> None:
    valid = (
        re.fullmatch(r"O[0-9]+", item_id)
        if provider == "vam"
        else _SAFE_LOC_ID.fullmatch(item_id)
        if provider in {"loc", "nasa"}
        else _SAFE_ID.fullmatch(item_id)
    )
    if not valid:
        raise SpiderError("invalid_asset", "素材 ID 无效")


def require_image_url(url: str, provider: str) -> None:
    allowed = _HOSTS.get(provider)
    if allowed is None:
        raise SpiderError("invalid_provider", "不支持此来源的图片下载")
    require_https_host(url, allowed)


class CuratedDownloader:
    def __init__(self, open_url: Callable[..., Any] = urlopen) -> None:
        self._open_url = open_url

    def read(self, url: str, provider: str) -> tuple[bytes, str]:
        allowed = _HOSTS.get(provider)
        if allowed is None:
            raise SpiderError("invalid_provider", "不支持此来源的图片下载")
        require_https_host(url, allowed)
        parts = urlsplit(url)
        url = urlunsplit(
            (
                parts.scheme,
                parts.netloc,
                # IIIF 尺寸中的逗号、感叹号是协议语法，AIC 不接受转义后的逗号。
                quote(
                    parts.path, safe="/%,!" if provider in {"artic", "vam"} else "/%"
                ),
                quote(parts.query, safe="=&%+/:,?"),
                "",
            )
        )
        request = Request(
            url, headers={"User-Agent": "TY-Image-Spider/2.4", "Accept": "image/*"}
        )
        try:
            with self._open_url(request, timeout=60) as response:
                require_https_host(response.geturl(), allowed)
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

    def download(
        self, url: str, provider: str, item_id: str, output_root: Path
    ) -> DownloadResult:
        validate_asset_id(provider, item_id)
        require_image_url(url, provider)
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
        payload, extension = self.read(url, provider)
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
