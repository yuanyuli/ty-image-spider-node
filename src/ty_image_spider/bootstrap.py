"""应用组合根：集中构造 Provider 与单用例服务。"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from pathlib import Path

from .cache import JsonCache
from .downloads import ImageDownloader
from .opencli import OpenCliRunner
from .providers.civitai import CivitaiProvider
from .providers.civitai_client import CivitaiClient
from .providers.local import LocalProvider
from .providers.registry import ProviderRegistry
from .providers.xiaohongshu import XiaohongshuProvider
from .services.detail import DetailService
from .services.download import DownloadService
from .services.search import SearchService
from .services.status import StatusService


@dataclass(frozen=True, slots=True)
class ApplicationServices:
    providers: ProviderRegistry
    search: SearchService
    detail: DetailService
    download: DownloadService
    status: StatusService


def build_services(output_root: Path, cache_root: Path) -> ApplicationServices:
    output = Path(output_root)
    cache = Path(cache_root)
    providers = ProviderRegistry()

    providers.register(
        CivitaiProvider(
            CivitaiClient(api_key=os.environ.get("CIVITAI_API_KEY", "")),
            JsonCache(cache / "civitai"),
            ImageDownloader(),
        )
    )
    providers.register(
        XiaohongshuProvider(
            OpenCliRunner(),
            JsonCache(cache / "xiaohongshu"),
            threading.Lock(),
        )
    )
    providers.register(LocalProvider(output))

    return ApplicationServices(
        providers=providers,
        search=SearchService(providers),
        detail=DetailService(providers),
        download=DownloadService(providers, output),
        status=StatusService(providers),
    )
