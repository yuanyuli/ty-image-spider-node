"""视频文件头识别，不执行网络或文件系统操作。"""


def detect_video_extension(header: bytes) -> str | None:
    if len(header) >= 12 and header[4:8] == b"ftyp":
        return ".mp4"
    if header.startswith(b"\x1a\x45\xdf\xa3"):
        return ".webm"
    if header.startswith(b"OggS"):
        return ".ogv"
    return None

