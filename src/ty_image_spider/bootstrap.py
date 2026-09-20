"""应用组合根：集中构造 Provider 与单用例服务。"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from pathlib import Path

from .cache import JsonCache
from .asset_index import AssetIndex
from .downloads import ImageDownloader
from .opencli import OpenCliRunner
from .providers.civitai import CivitaiProvider
from .providers.civitai_client import CivitaiClient
from .providers.behance import BehanceProvider
from .providers.artic import ArticProvider
from .providers.vam import VamProvider
from .providers.cleveland import ClevelandProvider
from .providers.museum_client import MuseumClient
from .providers.public_json_client import PublicJsonClient
from .providers.editorial import EditorialProvider
from .providers.editorial_sources import (
    APERTURE,
    COLOSSAL,
    DESIGN_MILK,
    FEATURE_SHOOT,
    MY_MODERN_MET,
    PRINT_MAGAZINE,
)
from .providers.arena import ArenaProvider
from .providers.loc import LocProvider
from .providers.nasa import NasaProvider
from .providers.curated_client import BehanceClient, FilmGrabClient
from .providers.curated_download import CuratedDownloader
from .providers.image_readers import ImageReaderRegistry
from .providers.filmgrab import FilmGrabProvider
from .providers.local import LocalProvider
from .providers.registry import ProviderRegistry
from .providers.wallhaven import WallhavenProvider
from .providers.wallhaven_client import WallhavenClient
from .providers.wallhaven_download import WallhavenDownloader
from .providers.xiaohongshu import XiaohongshuProvider
from .services.detail import DetailService
from .services.cache_job import CacheJobService
from .services.cache_progress import CacheProgress
from .services.download import DownloadService
from .services.search import SearchService
from .services.status import StatusService
from .services.opencli_connect import OpenCliConnectService
from .movies.credentials import TmdbCredentials
from .movies.tmdb import TmdbClient
from .movies.filmgrab_directory import FilmGrabDirectory
from .movies.mapping_store import MovieMappingStore
from .movies.resolution import MovieResolution


@dataclass(frozen=True, slots=True)
class ApplicationServices:
    providers: ProviderRegistry
    search: SearchService
    detail: DetailService
    download: DownloadService
    status: StatusService
    opencli_connect: OpenCliConnectService
    cache_job: CacheJobService


def build_services(output_root: Path, cache_root: Path) -> ApplicationServices:
    output = Path(output_root)
    cache = Path(cache_root)
    providers = ProviderRegistry()
    index = AssetIndex(output)
    reader = ImageReaderRegistry()

    providers.register(
        CivitaiProvider(
            CivitaiClient(api_key=os.environ.get("CIVITAI_API_KEY", "")),
            JsonCache(cache / "civitai"),
            ImageDownloader(),
            cached_asset=index.cached_original,
        )
    )
    providers.register(
        WallhavenProvider(
            WallhavenClient(),
            JsonCache(cache / "wallhaven"),
            WallhavenDownloader(),
        )
    )
    providers.register(BehanceProvider(BehanceClient()))
    for source in (
        COLOSSAL,
        DESIGN_MILK,
        FEATURE_SHOOT,
        MY_MODERN_MET,
        APERTURE,
        PRINT_MAGAZINE,
    ):
        providers.register(
            EditorialProvider(
                source,
                PublicJsonClient(
                    source.api_root, source.label, JsonCache(cache / source.id)
                ),
            )
        )
    providers.register(
        ArenaProvider(
            PublicJsonClient(
                "https://api.are.na/v2/", "Are.na", JsonCache(cache / "arena")
            ),
        )
    )
    providers.register(
        LocProvider(
            PublicJsonClient(
                "https://www.loc.gov/",
                "美国国会图书馆",
                JsonCache(cache / "loc"),
            ),
        )
    )
    providers.register(
        NasaProvider(
            PublicJsonClient(
                "https://images-api.nasa.gov/",
                "NASA",
                JsonCache(cache / "nasa"),
            ),
        )
    )
    filmgrab_client = FilmGrabClient()
    movies = MovieResolution(
        TmdbClient(
            TmdbCredentials(
                Path(__file__).resolve().parents[2] / ".local" / "tmdb.json"
            ),
            JsonCache(cache / "tmdb"),
        ),
        FilmGrabDirectory(filmgrab_client, JsonCache(cache / "film-directory")),
        MovieMappingStore(cache / "movie-mappings.sqlite3"),
    )
    providers.register(
        FilmGrabProvider(
            filmgrab_client, cache=JsonCache(cache / "filmgrab"), movies=movies
        )
    )
    providers.register(VamProvider(MuseumClient("vam", JsonCache(cache / "vam"))))
    providers.register(ArticProvider(MuseumClient("artic", JsonCache(cache / "artic"))))
    providers.register(
        ClevelandProvider(MuseumClient("cleveland", JsonCache(cache / "cleveland")))
    )
    opencli = OpenCliRunner()
    browser_lock = threading.Lock()
    providers.register(
        XiaohongshuProvider(
            opencli,
            JsonCache(cache / "xiaohongshu"),
            browser_lock,
        )
    )
    providers.register(LocalProvider(output))

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
        # 下载统一落到 ComfyUI output/ty-node，便于和旧节点及用户工作流约定保持一致。
        download=DownloadService(providers, output / "ty-node", index),
        status=StatusService(providers),
        opencli_connect=OpenCliConnectService(opencli, session_lock=browser_lock),
        cache_job=CacheJobService(
            search,
            detail,
            index,
            reader,
            frozenset(
                descriptor.id
                for descriptor in providers.descriptors()
                if descriptor.capabilities.cache
            ),
            CacheProgress(JsonCache(cache / "cache-progress")),
        ),
    )
