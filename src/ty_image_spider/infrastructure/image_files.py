"""下载目录中已落盘图片的验证与复用。"""

from pathlib import Path
from typing import Iterable

from PIL import Image


IMAGE_EXTENSIONS = (".jpg", ".png", ".webp", ".gif")


def find_valid_image(
    directory: Path,
    item_id: str,
    extensions: Iterable[str] = IMAGE_EXTENSIONS,
) -> Path | None:
    """返回同素材已存在的有效图片；损坏文件留给下载器原位替换。"""
    for extension in extensions:
        candidate = directory / f"{item_id}{extension}"
        if not candidate.is_file():
            continue
        try:
            with Image.open(candidate) as image:
                image.load()
        except (OSError, ValueError, SyntaxError):
            continue
        return candidate
    return None
