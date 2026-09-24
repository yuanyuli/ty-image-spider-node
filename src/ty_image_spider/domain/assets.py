"""素材及素材详情模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .errors import SpiderError
from .json_types import JsonValue


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
