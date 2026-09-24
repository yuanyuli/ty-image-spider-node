"""按素材领域注册 Provider 的无状态工厂函数。"""

from __future__ import annotations

import os
import threading
from pathlib import Path

from ..infrastructure.asset_index import AssetIndex
from ..infrastructure.cache import JsonCache
from ..infrastructure.downloads import ImageDownloader
from ..infrastructure.opencli import OpenCliRunner
from ..movies.credentials import TmdbCredentials
from ..movies.filmgrab_directory import FilmGrabDirectory
from ..movies.mapping_store import MovieMappingStore
from ..movies.resolution import MovieResolution
from ..movies.tmdb import TmdbClient
from ..providers.arena import ArenaProvider
from ..providers.artic import ArticProvider
from ..providers.behance import BehanceProvider
from ..providers.bizhi99 import Bizhi99Client, Bizhi99Provider
from ..providers.civitai import CivitaiProvider
from ..providers.civitai_client import CivitaiClient
from ..providers.cleveland import ClevelandProvider
from ..providers.commons import CommonsClient, CommonsProvider
from ..providers.curated_client import BehanceClient, FilmGrabClient
from ..providers.curated_download import CuratedDownloader
from ..providers.editorial import EditorialProvider
from ..providers.editorial_sources import (
    APERTURE,
    COLOSSAL,
    DESIGN_MILK,
    FEATURE_SHOOT,
    MY_MODERN_MET,
    PRINT_MAGAZINE,
)
from ..providers.filmgrab import FilmGrabProvider
from ..providers.loc import LocProvider
from ..providers.local import LocalProvider
from ..providers.met import MetClient, MetProvider
from ..providers.museum_client import MuseumClient
from ..providers.nasa import NasaProvider
from ..providers.netbian import NetbianClient, NetbianProvider
from ..providers.public_json_client import PublicJsonClient
from ..providers.registry import ProviderRegistry
from ..providers.tmdb_images import TmdbImageProvider
from ..providers.vam import VamProvider
from ..providers.wallhaven import WallhavenProvider
from ..providers.wallhaven_client import WallhavenClient
from ..providers.wallhaven_download import WallhavenDownloader
from ..providers.wallpaperscraft import WallpapersCraftClient, WallpapersCraftProvider
from ..providers.xiaohongshu import XiaohongshuProvider


def register_ai_providers(
    registry: ProviderRegistry, cache_root: Path, index: AssetIndex
) -> None:
    registry.register(
        CivitaiProvider(
            CivitaiClient(api_key=os.environ.get("CIVITAI_API_KEY", "")),
            JsonCache(cache_root / "civitai"),
            ImageDownloader(),
            cached_asset=index.cached_original,
        )
    )


def register_wallpaper_providers(
    registry: ProviderRegistry, cache_root: Path
) -> None:
    registry.register(
        WallhavenProvider(
            WallhavenClient(),
            JsonCache(cache_root / "wallhaven"),
            WallhavenDownloader(),
        )
    )
    registry.register(
        NetbianProvider(
            NetbianClient(),
            JsonCache(cache_root / "netbian"),
            CuratedDownloader(NetbianProvider.image_policy),
        )
    )
    registry.register(
        Bizhi99Provider(
            Bizhi99Client(),
            JsonCache(cache_root / "bizhi99"),
            CuratedDownloader(Bizhi99Provider.image_policy),
        )
    )
    registry.register(
        WallpapersCraftProvider(
            WallpapersCraftClient(),
            JsonCache(cache_root / "wallpaperscraft"),
            CuratedDownloader(WallpapersCraftProvider.image_policy),
        )
    )


def register_editorial_providers(
    registry: ProviderRegistry, cache_root: Path
) -> None:
    registry.register(BehanceProvider(BehanceClient()))
    for source in (
        COLOSSAL,
        DESIGN_MILK,
        FEATURE_SHOOT,
        MY_MODERN_MET,
        APERTURE,
        PRINT_MAGAZINE,
    ):
        registry.register(
            EditorialProvider(
                source,
                PublicJsonClient(
                    source.api_root,
                    source.label,
                    JsonCache(cache_root / source.id),
                ),
            )
        )
    registry.register(
        ArenaProvider(
            PublicJsonClient(
                "https://api.are.na/v2/",
                "Are.na",
                JsonCache(cache_root / "arena"),
            )
        )
    )


def register_archive_providers(
    registry: ProviderRegistry, cache_root: Path
) -> None:
    registry.register(
        LocProvider(
            PublicJsonClient(
                "https://www.loc.gov/",
                "美国国会图书馆",
                JsonCache(cache_root / "loc"),
            )
        )
    )
    registry.register(
        NasaProvider(
            PublicJsonClient(
                "https://images-api.nasa.gov/",
                "NASA",
                JsonCache(cache_root / "nasa"),
            )
        )
    )


def register_movie_providers(registry: ProviderRegistry, cache_root: Path) -> None:
    filmgrab_client = FilmGrabClient()
    tmdb_client = TmdbClient(
        TmdbCredentials(Path(__file__).resolve().parents[3] / ".local" / "tmdb.json"),
        JsonCache(cache_root / "tmdb"),
    )
    movies = MovieResolution(
        tmdb_client,
        FilmGrabDirectory(
            filmgrab_client, JsonCache(cache_root / "film-directory")
        ),
        MovieMappingStore(cache_root / "movie-mappings.sqlite3"),
    )
    registry.register(
        FilmGrabProvider(
            filmgrab_client,
            cache=JsonCache(cache_root / "filmgrab"),
            movies=movies,
        )
    )
    registry.register(
        TmdbImageProvider(tmdb_client, JsonCache(cache_root / "tmdb-images"))
    )


def register_collection_providers(
    registry: ProviderRegistry, cache_root: Path
) -> None:
    registry.register(VamProvider(MuseumClient("vam", JsonCache(cache_root / "vam"))))
    registry.register(
        ArticProvider(MuseumClient("artic", JsonCache(cache_root / "artic")))
    )
    registry.register(
        ClevelandProvider(
            MuseumClient("cleveland", JsonCache(cache_root / "cleveland"))
        )
    )
    registry.register(
        CommonsProvider(
            CommonsClient(JsonCache(cache_root / "commons")),
            CuratedDownloader(CommonsProvider.image_policy),
        )
    )
    registry.register(
        MetProvider(
            MetClient(
                PublicJsonClient(
                    "https://collectionapi.metmuseum.org/public/collection/v1/",
                    "纽约大都会艺术博物馆",
                    JsonCache(cache_root / "met"),
                )
            ),
            CuratedDownloader(MetProvider.image_policy),
        )
    )


def register_optional_providers(
    registry: ProviderRegistry,
    cache_root: Path,
    browser_lock: threading.Lock,
) -> OpenCliRunner:
    opencli = OpenCliRunner()
    registry.register(
        XiaohongshuProvider(
            opencli,
            JsonCache(cache_root / "xiaohongshu"),
            browser_lock,
        )
    )
    return opencli


def register_local_provider(registry: ProviderRegistry, output_root: Path) -> None:
    registry.register(LocalProvider(output_root))
