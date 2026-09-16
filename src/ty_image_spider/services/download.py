"""单项与整页下载用例。"""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

from ..models import AssetItem, DownloadResult, SpiderError
from ..providers.registry import ProviderRegistry


class DownloadService:
    def __init__(self, providers: ProviderRegistry, output_root: Path) -> None:
        self._providers = providers
        self._output_root = Path(output_root)

    def execute(self, payload: Mapping[str, object]) -> DownloadResult:
        item = AssetItem.from_untrusted(payload.get("item"))
        return self._providers.get(item.provider).download(item, self._output_root)

    def download_page(
        self, provider_id: str, raw_items: Sequence[object]
    ) -> DownloadResult:
        provider = self._providers.get(provider_id)
        if not provider.descriptor().capabilities.bulk_download:
            raise SpiderError("bulk_download_unsupported", "当前素材源不支持整页下载")
        if len(raw_items) > 20:
            raise SpiderError("bulk_download_limit", "一次最多下载 20 个素材")

        items = tuple(AssetItem.from_untrusted(value) for value in raw_items)
        if any(item.provider != provider_id for item in items):
            raise SpiderError("provider_mismatch", "素材来源与请求来源不一致")

        files: list[str] = []
        for item in items:
            files.extend(provider.download(item, self._output_root).files)
        return DownloadResult(tuple(files), f"已下载 {len(files)} 个文件")
