"""按来源、站点和素材 ID 持久索引已缓存的预览与详情。"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Iterator
from urllib.parse import urlencode

from .models import AssetDetail, AssetItem, JsonValue


class AssetIndex:
    def __init__(self, output_root: Path) -> None:
        self._output_root = Path(output_root).resolve()
        self._directory = self._output_root / "ty-node" / "ty-image-spider" / "cache"
        self._directory.mkdir(parents=True, exist_ok=True)
        self._database = self._directory / "index.sqlite3"
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS assets (key TEXT PRIMARY KEY, item_json TEXT NOT NULL, detail_json TEXT NOT NULL, file_name TEXT NOT NULL)"
            )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self._database, timeout=30)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    @staticmethod
    def _key(item: AssetItem) -> str:
        site = (
            str(item.metadata.get("site") or "") if item.provider == "civitai" else ""
        )
        return json.dumps([item.provider, site, item.id], ensure_ascii=False)

    def store(self, detail: AssetDetail, image: bytes, extension: str) -> None:
        item = detail.item
        if extension not in {".jpg", ".png", ".webp", ".gif"}:
            raise ValueError("unsupported cache image extension")
        key = self._key(item)
        file_name = hashlib.sha256(key.encode()).hexdigest() + extension
        target = self._directory / file_name
        descriptor, temp_name = tempfile.mkstemp(dir=self._directory, prefix=".cache-")
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(image)
            os.replace(temp_name, target)
        finally:
            Path(temp_name).unlink(missing_ok=True)
        with self._connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO assets VALUES (?, ?, ?, ?)",
                (
                    key,
                    json.dumps(item.to_dict(), ensure_ascii=False),
                    json.dumps(detail.to_dict(), ensure_ascii=False),
                    file_name,
                ),
            )

    def _lookup(
        self, item: AssetItem
    ) -> tuple[AssetItem, dict[str, JsonValue], str] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT item_json, detail_json, file_name FROM assets WHERE key = ?",
                (self._key(item),),
            ).fetchone()
        if row is None or not (self._directory / row[2]).is_file():
            return None
        try:
            stored = AssetItem.from_untrusted(json.loads(row[0]))
            detail = json.loads(row[1])
            if not isinstance(detail, dict):
                return None
            relative = (self._directory / row[2]).relative_to(self._output_root)
            url = "/view?" + urlencode(
                {
                    "filename": relative.name,
                    "subfolder": relative.parent.as_posix(),
                    "type": "output",
                }
            )
            return stored, detail, url
        except (ValueError, TypeError, KeyError):
            return None

    def overlay(self, fresh: AssetItem) -> AssetItem:
        hit = self._lookup(fresh)
        if hit is None:
            return fresh
        stored, _, url = hit
        return replace(
            stored, preview_url=url, source_url=fresh.source_url or stored.source_url
        )

    def contains(self, item: AssetItem) -> bool:
        return self._lookup(item) is not None

    def original(self, item: AssetItem) -> AssetItem:
        return self.cached_original(item) or item

    def cached_original(self, item: AssetItem) -> AssetItem | None:
        hit = self._lookup(item)
        if hit is None:
            return None
        stored, _, _ = hit
        return replace(stored, source_url=item.source_url or stored.source_url)

    def detail(self, item: AssetItem) -> AssetDetail | None:
        hit = self._lookup(item)
        if hit is None:
            return None
        stored, data, url = hit
        images = data.get("images")
        resolved_images = (
            tuple(
                url if value == stored.preview_url else value
                for value in images
                if isinstance(value, str)
            )
            if isinstance(images, list)
            else ()
        )
        metadata = data.get("metadata")
        return AssetDetail(
            self.overlay(item),
            resolved_images or (url,),
            content=str(data.get("content") or ""),
            workflow=data.get("workflow"),
            metadata=metadata if isinstance(metadata, dict) else {},
        )
