"""搜索与下载用例的输入输出模型。"""

from dataclasses import dataclass, field
from typing import Mapping

from .assets import AssetItem
from .json_types import JsonValue
from .providers import ProviderStatus


@dataclass(frozen=True, slots=True)
class SearchRequest:
    provider: str
    query: str = ""
    filters: Mapping[str, JsonValue] = field(default_factory=dict)
    cursor: str | None = None
    refresh: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "filters", dict(self.filters))


@dataclass(frozen=True, slots=True)
class SearchPage:
    items: tuple[AssetItem, ...] = ()
    next_cursor: str | None = None
    stale: bool = False
    status: ProviderStatus | None = None
    message: str = ""
    choices: tuple[Mapping[str, JsonValue], ...] = ()

    def to_dict(self) -> dict[str, JsonValue]:
        result: dict[str, JsonValue] = {
            "items": [item.to_dict() for item in self.items],
            "stale": self.stale,
            "message": self.message,
        }
        if self.next_cursor is not None:
            result["next_cursor"] = self.next_cursor
        if self.status is not None:
            result["status"] = self.status.to_dict()
        if self.choices:
            result["choices"] = [dict(choice) for choice in self.choices]
        return result


@dataclass(frozen=True, slots=True)
class DownloadResult:
    files: tuple[str, ...] = ()
    message: str = ""
    output_root: str = ""

    def to_dict(self) -> dict[str, JsonValue]:
        result: dict[str, JsonValue] = {
            "files": list(self.files),
            "message": self.message,
        }
        if self.output_root:
            result["output_root"] = self.output_root
        return result
