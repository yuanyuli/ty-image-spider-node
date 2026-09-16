"""TY Image Spider 业务包。"""

from .nodes import TyImageSpider


NODE_CLASS_MAPPINGS = {"TyImageSpider": TyImageSpider}
NODE_DISPLAY_NAME_MAPPINGS = {"TyImageSpider": "TY Image Spider · 素材浏览"}
WEB_DIRECTORY = "./web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]

