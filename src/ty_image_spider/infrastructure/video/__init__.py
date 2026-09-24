"""受策略约束的视频下载基础设施，不包含具体素材来源。"""

from .downloader import VideoDownloader
from .files import find_valid_video
from .policy import VideoDownloadPolicy
from .signatures import detect_video_extension

__all__ = [
    "VideoDownloader",
    "VideoDownloadPolicy",
    "detect_video_extension",
    "find_valid_video",
]
