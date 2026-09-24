"""应用层提供给 HTTP 适配器的用例集合。"""

from dataclasses import dataclass

from ..providers.shared import ProviderRegistry
from ..services.cache_job import CacheJobService
from ..services.detail import DetailService
from ..services.download import DownloadService
from ..services.opencli_connect import OpenCliConnectService
from ..services.search import SearchService
from ..services.status import StatusService


@dataclass(frozen=True, slots=True)
class ApplicationServices:
    providers: ProviderRegistry
    search: SearchService
    detail: DetailService
    download: DownloadService
    status: StatusService
    opencli_connect: OpenCliConnectService
    cache_job: CacheJobService
