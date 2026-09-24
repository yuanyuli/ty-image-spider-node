"""素材来源的描述、筛选与状态模型。"""

from dataclasses import dataclass, field

from .json_types import JsonValue


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
class ProviderPresentation:
    """来源自行声明展示信息，前端无需维护来源映射。"""

    group_id: str
    group_label: str
    short_label: str
    detail_label: str
    group_order: int
    source_order: int
    cache_description: str = ""
    visible: bool = True

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "group_id": self.group_id,
            "group_label": self.group_label,
            "short_label": self.short_label,
            "detail_label": self.detail_label,
            "group_order": self.group_order,
            "source_order": self.source_order,
            "cache_description": self.cache_description,
            "visible": self.visible,
        }


@dataclass(frozen=True, slots=True)
class ProviderDescriptor:
    id: str
    label: str
    presentation: ProviderPresentation = field(kw_only=True)
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
            "presentation": self.presentation.to_dict(),
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
