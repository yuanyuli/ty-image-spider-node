"""图片素材浏览的单用例应用服务。"""

from .detail import DetailService
from .download import DownloadService
from .search import SearchService
from .status import StatusService

__all__ = ["DetailService", "DownloadService", "SearchService", "StatusService"]
