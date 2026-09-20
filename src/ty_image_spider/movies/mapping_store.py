"""持久化已确认的 TMDB 电影与 FilmGrab 文章映射。"""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any


class MovieMappingStore:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path = path
        with closing(sqlite3.connect(path)) as connection, connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS mappings (movie_id INTEGER PRIMARY KEY, payload TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS aliases (query TEXT PRIMARY KEY, movie_id INTEGER NOT NULL)"
            )

    def get(self, movie_id: int) -> dict[str, Any] | None:
        with closing(sqlite3.connect(self._path, timeout=10)) as connection:
            row = connection.execute(
                "SELECT payload FROM mappings WHERE movie_id=?", (movie_id,)
            ).fetchone()
        return json.loads(row[0]) if row else None

    def find(self, query: str) -> dict[str, Any] | None:
        with closing(sqlite3.connect(self._path, timeout=10)) as connection:
            row = connection.execute(
                "SELECT m.payload FROM aliases a JOIN mappings m ON a.movie_id=m.movie_id WHERE a.query=?",
                (query.strip().casefold(),),
            ).fetchone()
        return json.loads(row[0]) if row else None

    def save(
        self, query: str, movie: dict[str, Any], post: dict[str, Any]
    ) -> dict[str, Any]:
        mapping = {"movie": movie, "post": post}
        with closing(sqlite3.connect(self._path, timeout=10)) as connection, connection:
            connection.execute(
                "INSERT OR REPLACE INTO mappings VALUES (?,?)",
                (movie["id"], json.dumps(mapping, ensure_ascii=False)),
            )
            connection.execute(
                "INSERT OR REPLACE INTO aliases VALUES (?,?)",
                (query.strip().casefold(), movie["id"]),
            )
        return mapping
