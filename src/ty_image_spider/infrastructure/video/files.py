"""下载目录中已有视频文件的签名验证与复用。"""

from pathlib import Path

from .signatures import detect_video_extension


VIDEO_EXTENSIONS = (".mp4", ".webm", ".ogv")


def find_valid_video(directory: Path, item_id: str) -> Path | None:
    for extension in VIDEO_EXTENSIONS:
        candidate = directory / f"{item_id}{extension}"
        if not candidate.is_file():
            continue
        try:
            with candidate.open("rb") as handle:
                detected = detect_video_extension(handle.read(64))
        except OSError:
            continue
        if detected == extension:
            return candidate
    return None

