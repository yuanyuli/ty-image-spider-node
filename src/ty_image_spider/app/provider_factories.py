"""按素材领域注册 Provider 的无状态工厂函数。"""

from __future__ import annotations

import os
import threading
from pathlib import Path

from ..infrastructure.asset_index import AssetIndex
from ..infrastructure.cache import JsonCache
from ..infrastructure.downloads import ImageDownloader
from ..infrastructure.opencli import OpenCliRunner
from ..infrastructure.video import VideoDownloader, VideoDownloadPolicy
from ..movies.credentials import TmdbCredentials
from ..movies.filmgrab_directory import FilmGrabDirectory
from ..movies.mapping_store import MovieMappingStore
from ..movies.resolution import MovieResolution
from ..movies.tmdb import TmdbClient
from ..providers.ai import CivitaiClient, CivitaiProvider, XiaohongshuProvider
from ..providers.collections import (
    ArticProvider,
    ClevelandProvider,
    CommonsClient,
    CommonsProvider,
    LocProvider,
    MetClient,
    MetProvider,
    MuseumClient,
    NasaProvider,
    VamProvider,
)
from ..providers.editorial import (
    APERTURE,
    COLOSSAL,
    DESIGN_MILK,
    FEATURE_SHOOT,
    MY_MODERN_MET,
    PRINT_MAGAZINE,
    ArenaProvider,
    BehanceProvider,
    EditorialProvider,
)
from ..providers.local import LocalProvider
from ..providers.movies import FilmGrabProvider, TmdbImageProvider
from ..providers.shared import (
    BehanceClient,
    CuratedDownloader,
    FilmGrabClient,
    ProviderRegistry,
    PublicJsonClient,
)
from ..providers.wallpapers import (
    Bizhi99Client,
    Bizhi99Provider,
    NetbianClient,
    NetbianProvider,
    WallhavenClient,
    WallhavenDownloader,
    WallhavenProvider,
    WallpapersCraftClient,
    WallpapersCraftProvider,
)
from ..providers.videos import (
    CommonsVideoClient,
    CommonsVideoProvider,
    NasaVideoClient,
    NasaVideoProvider,
    PrelingerClient,
    PrelingerProvider,
)


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


def register_wallpaper_providers(registry: ProviderRegistry, cache_root: Path) -> None:
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


def register_editorial_providers(registry: ProviderRegistry, cache_root: Path) -> None:
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


def register_archive_providers(registry: ProviderRegistry, cache_root: Path) -> None:
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
        FilmGrabDirectory(filmgrab_client, JsonCache(cache_root / "film-directory")),
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


def register_collection_providers(registry: ProviderRegistry, cache_root: Path) -> None:
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


def register_video_providers(registry: ProviderRegistry, cache_root: Path) -> None:
    """构造并注册独立视频来源；只在组合根绑定具体下载策略。"""
    prelinger_policy = VideoDownloadPolicy(
        "prelinger",
        lambda host: host == "archive.org",
        r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}",
    )
    commons_policy = VideoDownloadPolicy(
        "commons-video",
        lambda host: host == "upload.wikimedia.org",
        r"[1-9][0-9]*",
    )
    nasa_policy = VideoDownloadPolicy(
        "nasa-video",
        lambda host: host == "images-assets.nasa.gov",
        r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}",
    )
    registry.register(
        PrelingerProvider(
            PrelingerClient(JsonCache(cache_root / "prelinger")),
            VideoDownloader(prelinger_policy),
        )
    )
    registry.register(
        CommonsVideoProvider(
            CommonsVideoClient(JsonCache(cache_root / "commons-video")),
            VideoDownloader(commons_policy),
        )
    )
    registry.register(
        NasaVideoProvider(
            NasaVideoClient(JsonCache(cache_root / "nasa-video")),
            VideoDownloader(nasa_policy),
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
