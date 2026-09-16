"""ComfyUI 输出目录中的本地素材历史策略。"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

from ..metadata import extract_prompts, read_image_metadata
from ..models import (
    AssetDetail,
    AssetItem,
    DownloadResult,
    FilterField,
    ProviderCapabilities,
    ProviderDescriptor,
    ProviderStatus,
    SearchPage,
    SearchRequest,
    SpiderError,
)
from ..security import resolve_inside


_ROOT_NAMES = ("ty-image-spider", "ty-node")
_IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp"})


class LocalProvider:
    id = "local"

    def __init__(self, output_root: Path) -> None:
        self._output_root = Path(output_root).resolve()

    def descriptor(self) -> ProviderDescriptor:
        return ProviderDescriptor(
            id=self.id,
            label="本地历史",
            description="浏览 TY Image Spider 与旧节点下载的本地图片",
            filters=(
                FilterField("only_with_prompt", "仅含提示词", "toggle", False),
                FilterField("count", "数量", "number", 24, minimum=1, maximum=100),
            ),
            capabilities=ProviderCapabilities(download=False, bulk_download=False),
        )

    def status(self) -> ProviderStatus:
        return ProviderStatus(True)

    def search(self, request: SearchRequest) -> SearchPage:
        count = request.filters.get("count", 24)
        count = count if isinstance(count, int) and not isinstance(count, bool) else 24
        count = max(1, min(count, 100))
        offset = self._offset(request.cursor)
        needle = request.query.strip().casefold()
        only_with_prompt = bool(request.filters.get("only_with_prompt", False))

        indexed: list[tuple[int, str, AssetItem]] = []
        for root_name in _ROOT_NAMES:
            indexed.extend(self._scan_root(root_name, needle, only_with_prompt))
        indexed.sort(key=lambda entry: (-entry[0], entry[1]))

        selected = tuple(item for _, _, item in indexed[offset : offset + count])
        next_offset = offset + count
        next_cursor = str(next_offset) if next_offset < len(indexed) else None
        return SearchPage(selected, next_cursor)

    def detail(self, item: AssetItem) -> AssetDetail:
        path = self._item_path(item)
        metadata = read_image_metadata(path)
        return AssetDetail(
            item,
            (item.preview_url,) if item.preview_url else (),
            metadata=metadata,
        )

    def download(self, item: AssetItem, output_root: Path) -> DownloadResult:
        self._item_path(item)
        raise SpiderError("local_download_unneeded", "本地素材无需下载")

    def _scan_root(
        self, root_name: str, needle: str, only_with_prompt: bool
    ) -> list[tuple[int, str, AssetItem]]:
        root = (self._output_root / root_name).resolve()
        if root.parent != self._output_root or not root.is_dir():
            return []
        indexed: list[tuple[int, str, AssetItem]] = []
        try:
            candidates = root.rglob("*")
            for path in candidates:
                entry = self._index_path(root, path, needle, only_with_prompt)
                if entry is not None:
                    indexed.append(entry)
        except OSError:
            return indexed
        return indexed

    def _index_path(
        self, root: Path, path: Path, needle: str, only_with_prompt: bool
    ) -> tuple[int, str, AssetItem] | None:
        try:
            if (
                path.is_symlink()
                or not path.is_file()
                or path.suffix.casefold() not in _IMAGE_EXTENSIONS
            ):
                return None
            resolved = path.resolve(strict=True)
            resolved.relative_to(root)
            metadata = read_image_metadata(resolved)
            if not metadata:
                return None
            prompt, negative = extract_prompts(metadata)
            if only_with_prompt and not prompt:
                return None
            if (
                needle
                and needle not in path.name.casefold()
                and needle not in prompt.casefold()
            ):
                return None
            stat = resolved.stat()
            relative = resolved.relative_to(self._output_root)
            item = AssetItem(
                provider=self.id,
                id=relative.as_posix(),
                preview_url=_view_url(resolved, self._output_root),
                title=path.name,
                created_at=datetime.fromtimestamp(
                    stat.st_mtime, timezone.utc
                ).isoformat(),
                width=_integer(metadata.get("width")),
                height=_integer(metadata.get("height")),
                has_prompt=bool(prompt),
                prompt=prompt or None,
                negative_prompt=negative or None,
                stats={"size_bytes": stat.st_size},
                metadata={**metadata, "relative_path": relative.as_posix()},
                download_mode="none",
            )
            return stat.st_mtime_ns, relative.as_posix().casefold(), item
        except (OSError, ValueError):
            return None

    def _item_path(self, item: AssetItem) -> Path:
        if item.provider != self.id:
            raise SpiderError("invalid_asset", "本地素材数据无效")
        path = resolve_inside(self._output_root, Path(item.id))
        try:
            relative = path.relative_to(self._output_root)
        except ValueError as exc:
            raise SpiderError("invalid_asset", "本地素材路径无效") from exc
        if not relative.parts or relative.parts[0] not in _ROOT_NAMES:
            raise SpiderError("invalid_asset", "本地素材路径无效")
        if (
            path.is_symlink()
            or not path.is_file()
            or path.suffix.casefold() not in _IMAGE_EXTENSIONS
        ):
            raise SpiderError("asset_not_found", "本地素材不存在", status=404)
        return path

    @staticmethod
    def _offset(cursor: str | None) -> int:
        if cursor is None:
            return 0
        try:
            offset = int(cursor)
        except (TypeError, ValueError) as exc:
            raise SpiderError("invalid_cursor", "本地历史分页游标无效") from exc
        if offset < 0:
            raise SpiderError("invalid_cursor", "本地历史分页游标无效")
        return offset


def _view_url(path: Path, output_root: Path) -> str:
    relative = path.relative_to(output_root)
    return "/view?" + urlencode(
        {
            "filename": relative.name,
            "subfolder": relative.parent.as_posix()
            if relative.parent != Path(".")
            else "",
            "type": "output",
        }
    )


def _integer(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None
