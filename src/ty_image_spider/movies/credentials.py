"""只在服务器端读取 TMDB 访问令牌。"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Mapping

from ..models import SpiderError


class TmdbCredentials:
    def __init__(
        self, path: Path, environment: Mapping[str, str] | None = None
    ) -> None:
        self.path = path
        self._environment = os.environ if environment is None else environment

    def read(self) -> str:
        token = self._environment.get("TMDB_READ_ACCESS_TOKEN", "").strip()
        if token:
            return token
        if not self.path.is_file():
            return ""
        try:
            data = json.loads(self.path.read_text(encoding="utf-8-sig"))
            token = data.get("read_access_token", "")
            if not isinstance(token, str):
                raise ValueError("invalid token type")
            return token.strip()
        except (OSError, ValueError, AttributeError) as exc:
            raise SpiderError(
                "tmdb_config_invalid", "TMDB 本地配置格式无效，请检查 tmdb.json"
            ) from exc
