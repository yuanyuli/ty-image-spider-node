"""可稳定映射到外部响应的领域错误。"""

from typing import Mapping

from .json_types import JsonValue


class SpiderError(Exception):
    """可以稳定映射到 HTTP 与前端状态的领域错误。"""

    def __init__(
        self,
        code: str,
        message: str,
        action: str = "",
        status: int = 400,
        *,
        details: Mapping[str, JsonValue] | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.action = action
        self.status = status
        self.details = dict(details or {})
