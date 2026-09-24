"""Civitai 字段标准化与提示词分类。"""

from typing import Any, Mapping

from ....domain import AssetItem
from ....infrastructure.metadata import extract_prompts


def integer_or_none(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def metadata_classification(prompt: str, metadata: Mapping[str, Any]) -> str:
    """沿用旧节点 A/B/C 规则，同时忽略本节点附加的辅助字段。"""
    if metadata.get("workflow"):
        return "A"
    if prompt or any(
        key not in {"site", "models", "loras", "classification"} for key in metadata
    ):
        return "B"
    return "C"


def normalize(raw: Mapping[str, Any], site: str) -> AssetItem:
    item_id = str(raw.get("id", ""))
    raw_meta = raw.get("meta")
    meta: Mapping[str, Any] = raw_meta if isinstance(raw_meta, Mapping) else {}
    prompt, negative = extract_prompts(meta)
    resources = meta.get("resources", [])
    models: list[dict[str, str]] = []
    loras: list[dict[str, str]] = []
    if isinstance(resources, list):
        for resource in resources:
            if not isinstance(resource, Mapping):
                continue
            resource_type = str(resource.get("type", "")).lower()
            name = resource.get("name")
            if not isinstance(name, str) or not name:
                continue
            normalized = {"type": resource_type, "name": name}
            if resource_type == "model":
                models.append(normalized)
            elif resource_type == "lora":
                loras.append(normalized)
    metadata: dict[str, Any] = dict(meta)
    metadata.update({"site": site, "models": models, "loras": loras})
    metadata["classification"] = metadata_classification(prompt, meta)
    source_url = f"https://{site}/images/{item_id}" if item_id else None
    return AssetItem(
        provider="civitai",
        id=item_id,
        preview_url=str(raw["url"]) if raw.get("url") else None,
        source_url=source_url,
        author=str(raw["username"]) if raw.get("username") else None,
        created_at=str(raw["createdAt"]) if raw.get("createdAt") else None,
        width=integer_or_none(raw.get("width")),
        height=integer_or_none(raw.get("height")),
        has_prompt=bool(prompt),
        prompt=prompt or None,
        negative_prompt=negative or None,
        stats=dict(raw["stats"]) if isinstance(raw.get("stats"), Mapping) else {},
        metadata=metadata,
        download_mode="single",
    )
