"""独立视频素材来源包；注册行为由应用装配层负责。"""

from .commons import CommonsVideoClient, CommonsVideoProvider
from .nasa import NasaVideoClient, NasaVideoProvider
from .prelinger import PrelingerClient, PrelingerProvider, is_archive_download_host

__all__ = [
    "CommonsVideoClient",
    "CommonsVideoProvider",
    "NasaVideoClient",
    "NasaVideoProvider",
    "PrelingerClient",
    "PrelingerProvider",
    "is_archive_download_host",
]
