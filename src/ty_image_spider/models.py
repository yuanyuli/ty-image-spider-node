"""跨 Provider 传递的稳定领域模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, TypeAlias


JsonValue: TypeAlias = (
    None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
)


class SpiderError(Exception):
    """可以稳定映射到 HTTP 与前端状态的领域错误。"""

    def __init__(self, code: str, message: str, action: str = "", status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.action = action
        self.status = status


@dataclass(frozen=True, slots=True)
class FilterOption:
    value: str
    label: str

    def to_dict(self) -> dict[str, JsonValue]:
        return {"value": self.value, "label": self.label}


@dataclass(frozen=True, slots=True)
class FilterField:
    name: str
    label: str
    kind: str
    default: JsonValue = None
    options: tuple[FilterOption, ...] = ()
    minimum: int | None = None
    maximum: int | None = None
    placeholder: str = ""

    def to_dict(self) -> dict[str, JsonValue]:
        result: dict[str, JsonValue] = {
            "name": self.name,
            "label": self.label,
            "kind": self.kind,
            "default": self.default,
            "options": [option.to_dict() for option in self.options],
        }
        if self.minimum is not None:
            result["minimum"] = self.minimum
        if self.maximum is not None:
            result["maximum"] = self.maximum
        if self.placeholder:
            result["placeholder"] = self.placeholder
        return result


@dataclass(frozen=True, slots=True)
class ProviderCapabilities:
    detail: bool = True
    download: bool = True
    bulk_download: bool = False
    pagination: str = "cursor"
    cache: bool = False
    movie_lookup: bool = False

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "detail": self.detail,
            "download": self.download,
            "bulk_download": self.bulk_download,
            "pagination": self.pagination,
            "cache": self.cache,
            "movie_lookup": self.movie_lookup,
        }


@dataclass(frozen=True, slots=True)
class ProviderDescriptor:
    id: str
    label: str
    description: str = ""
    filters: tuple[FilterField, ...] = ()
    capabilities: ProviderCapabilities = field(default_factory=ProviderCapabilities)
    search_presets: tuple[FilterOption, ...] = ()
    search_placeholder: str = ""

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "id": self.id,
            "label": self.label,
            "description": self.description,
            "filters": [item.to_dict() for item in self.filters],
            "capabilities": self.capabilities.to_dict(),
            "search_presets": [option.to_dict() for option in self.search_presets],
            "search_placeholder": self.search_placeholder,
        }


@dataclass(frozen=True, slots=True)
class ProviderStatus:
    available: bool
    code: str = "ready"
    message: str = ""
    action: str = ""

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "available": self.available,
            "code": self.code,
            "message": self.message,
            "action": self.action,
        }


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
class AssetItem:
    provider: str
    id: str
    kind: str = "image"
    preview_url: str | None = None
    source_url: str | None = None
    title: str | None = None
    author: str | None = None
    created_at: str | None = None
    width: int | None = None
    height: int | None = None
    has_prompt: bool = False
    prompt: str | None = None
    negative_prompt: str | None = None
    image_count: int = 1
    stats: Mapping[str, JsonValue] = field(default_factory=dict)
    tags: tuple[str, ...] = ()
    metadata: Mapping[str, JsonValue] = field(default_factory=dict)
    download_mode: str = "single"

    def __post_init__(self) -> None:
        object.__setattr__(self, "stats", dict(self.stats))
        object.__setattr__(self, "tags", tuple(self.tags))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, JsonValue]:
        result: dict[str, JsonValue] = {
            "provider": self.provider,
            "id": self.id,
            "kind": self.kind,
            "has_prompt": self.has_prompt,
            "image_count": self.image_count,
            "stats": dict(self.stats),
            "tags": list(self.tags),
            "metadata": dict(self.metadata),
            "download_mode": self.download_mode,
        }
        for name in (
            "preview_url",
            "source_url",
            "title",
            "author",
            "created_at",
            "width",
            "height",
            "prompt",
            "negative_prompt",
        ):
            value = getattr(self, name)
            if value is not None:
                result[name] = value
        return result

    @classmethod
    def from_untrusted(cls, value: object) -> "AssetItem":
        if not isinstance(value, Mapping):
            raise SpiderError("invalid_asset", "素材数据必须是对象")
        provider = value.get("provider")
        item_id = value.get("id")
        if (
            not isinstance(provider, str)
            or not provider
            or not isinstance(item_id, str)
            or not item_id
        ):
            raise SpiderError("invalid_asset", "素材数据缺少有效的来源或 ID")

        string_fields = (
            "kind",
            "preview_url",
            "source_url",
            "title",
            "author",
            "created_at",
            "prompt",
            "negative_prompt",
            "download_mode",
        )
        kwargs: dict[str, Any] = {"provider": provider, "id": item_id}
        for name in string_fields:
            raw = value.get(name)
            if raw is not None:
                if not isinstance(raw, str):
                    raise SpiderError(
                        "invalid_asset", f"素材数据字段 {name} 必须是字符串"
                    )
                kwargs[name] = raw
        for name in ("width", "height", "image_count"):
            raw = value.get(name)
            if raw is not None:
                if not isinstance(raw, int) or isinstance(raw, bool):
                    raise SpiderError(
                        "invalid_asset", f"素材数据字段 {name} 必须是整数"
                    )
                kwargs[name] = raw
        has_prompt = value.get("has_prompt")
        if has_prompt is not None:
            if not isinstance(has_prompt, bool):
                raise SpiderError(
                    "invalid_asset", "素材数据字段 has_prompt 必须是布尔值"
                )
            kwargs["has_prompt"] = has_prompt
        for name in ("stats", "metadata"):
            raw = value.get(name)
            if raw is not None:
                if not isinstance(raw, Mapping):
                    raise SpiderError(
                        "invalid_asset", f"素材数据字段 {name} 必须是对象"
                    )
                kwargs[name] = dict(raw)
        tags = value.get("tags")
        if tags is not None:
            if not isinstance(tags, (list, tuple)) or not all(
                isinstance(tag, str) for tag in tags
            ):
                raise SpiderError("invalid_asset", "素材数据字段 tags 必须是字符串数组")
            kwargs["tags"] = tuple(tags)
        return cls(**kwargs)


@dataclass(frozen=True, slots=True)
class AssetDetail:
    item: AssetItem
    images: tuple[str, ...] = ()
    content: str = ""
    workflow: JsonValue = None
    metadata: Mapping[str, JsonValue] = field(default_factory=dict)

    def to_dict(self) -> dict[str, JsonValue]:
        result: dict[str, JsonValue] = {
            "item": self.item.to_dict(),
            "images": list(self.images),
            "content": self.content,
            "metadata": dict(self.metadata),
        }
        if self.workflow is not None:
            result["workflow"] = self.workflow
        return result


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
