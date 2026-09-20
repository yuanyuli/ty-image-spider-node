"""ComfyUI 零输出节点适配。"""

from __future__ import annotations


class TyImageSpider:
    OUTPUT_NODE = True
    RETURN_TYPES = ()
    RETURN_NAMES = ()
    FUNCTION = "browse"
    CATEGORY = "TY Utils/素材浏览"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, tuple[str, dict[str, object]]]]:
        return {
            "required": {
                "state_json": (
                    "STRING",
                    {"default": "{}", "multiline": False, "hidden": True},
                )
            }
        }

    @classmethod
    def IS_CHANGED(cls, state_json: object = "{}") -> str:
        return state_json if isinstance(state_json, str) else "{}"

    def browse(self, state_json: object = "{}") -> dict[str, dict[str, list[str]]]:
        serialized = state_json if isinstance(state_json, str) else "{}"
        return {"ui": {"state": [serialized]}}
