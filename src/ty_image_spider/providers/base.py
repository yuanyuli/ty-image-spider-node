"""素材来源策略协议。"""

from __future__ import annotations

from pathlib import Path
from .download_policy import DownloadPolicy
from typing import Protocol

from ..models import (
    AssetDetail,
    AssetItem,
    DownloadResult,
    ProviderDescriptor,
    ProviderStatus,
    SearchPage,
    SearchRequest,
)


class AssetProvider(Protocol):
    id: str

    @property
    def image_policy(self) -> DownloadPolicy | None: ...

    def descriptor(self) -> ProviderDescriptor: ...

    def status(self) -> ProviderStatus: ...

    def search(self, request: SearchRequest) -> SearchPage: ...

    def detail(self, item: AssetItem) -> AssetDetail: ...

    def download(self, item: AssetItem, output_root: Path) -> DownloadResult: ...
