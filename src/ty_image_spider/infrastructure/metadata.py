"""图片 metadata 读取与提示词识别。"""

from __future__ import annotations

import json
import warnings
from pathlib import Path
from typing import Any, Mapping

from PIL import Image


MAX_IMAGE_PIXELS = 50_000_000


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, bytes):
        for encoding in ("utf-8", "utf-16-le", "latin-1"):
            try:
                return value.decode(encoding)
            except UnicodeDecodeError:
                continue
        return ""
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return str(value)


def read_image_metadata(path: Path) -> dict[str, Any]:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path) as image:
                if image.width * image.height > MAX_IMAGE_PIXELS:
                    return {}
                result = {
                    str(key): _json_safe(value) for key, value in image.info.items()
                }
                result["width"] = image.width
                result["height"] = image.height
                result["format"] = image.format or ""
                return result
    except (
        OSError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ):
        return {}


def _looks_like_workflow(value: str) -> bool:
    stripped = value.strip()
    if not stripped or stripped[0] not in "[{":
        return False
    try:
        parsed = json.loads(stripped)
    except (TypeError, ValueError):
        return False
    if isinstance(parsed, list):
        return True
    return isinstance(parsed, dict) and any(
        key in parsed for key in ("nodes", "workflow")
    )


def _first_string(metadata: Mapping[str, Any], names: tuple[str, ...]) -> str:
    for name in names:
        value = metadata.get(name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def extract_prompts(metadata: Mapping[str, Any]) -> tuple[str, str]:
    prompt = _first_string(metadata, ("prompt", "positive_prompt", "positivePrompt"))
    negative = _first_string(
        metadata,
        ("negative_prompt", "negativePrompt", "negative"),
    )
    if prompt and _looks_like_workflow(prompt):
        return "", ""
    return prompt, negative
