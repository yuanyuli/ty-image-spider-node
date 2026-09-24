"""应用组合根：构造 Provider、共享基础设施与单用例服务。"""

from __future__ import annotations

import threading
from pathlib import Path

from ..infrastructure.asset_index import AssetIndex
from ..infrastructure.cache import JsonCache
from ..providers.curated_download import CuratedDownloader
from ..providers.image_readers import ImageReaderRegistry
from ..providers.registry import ProviderRegistry
from ..services.cache_job import CacheJobService
from ..services.cache_progress import CacheProgress
from ..services.cache_runner import CacheJobRunner
from ..services.detail import DetailService
from ..services.download import DownloadService
from ..services.opencli_connect import OpenCliConnectService
from ..services.search import SearchService
from ..services.status import StatusService
from .provider_factories import (
    register_ai_providers,
    register_archive_providers,
    register_collection_providers,
    register_editorial_providers,
    register_local_provider,
    register_movie_providers,
    register_optional_providers,
    register_wallpaper_providers,
)
from .services import ApplicationServices


def build_services(output_root: Path, cache_root: Path) -> ApplicationServices:
    output = Path(output_root)
    cache = Path(cache_root)
    providers = ProviderRegistry()
    index = AssetIndex(output)
    reader = ImageReaderRegistry()
    browser_lock = threading.Lock()

    register_ai_providers(providers, cache, index)
    register_wallpaper_providers(providers, cache)
    register_editorial_providers(providers, cache)
    register_archive_providers(providers, cache)
    register_movie_providers(providers, cache)
    register_collection_providers(providers, cache)
    opencli = register_optional_providers(providers, cache, browser_lock)
    register_local_provider(providers, output)

    for provider in providers.all():
        policy = provider.image_policy
        if policy is not None and provider.descriptor().capabilities.cache:
            reader.register(provider.id, CuratedDownloader(policy))

    search = SearchService(providers, index)
    detail = DetailService(providers, index)
    return ApplicationServices(
        providers=providers,
        search=search,
        detail=detail,
        download=DownloadService(providers, output / "ty-node", index),
        status=StatusService(providers),
        opencli_connect=OpenCliConnectService(opencli, session_lock=browser_lock),
        cache_job=CacheJobService(
            CacheJobRunner(
                search,
                detail,
                index,
                reader,
                CacheProgress(JsonCache(cache / "cache-progress")),
            ),
            frozenset(
                descriptor.id
                for descriptor in providers.descriptors()
                if descriptor.capabilities.cache
            ),
        ),
    )
