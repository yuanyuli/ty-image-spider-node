"""记录错误类别与源码位置，不记录上游异常文本、请求或局部变量。"""

from __future__ import annotations

import logging
import traceback
from pathlib import Path


def log_failure(logger: logging.Logger, context: str, error: BaseException) -> None:
    frames = traceback.extract_tb(error.__traceback__)[-6:]
    locations = " > ".join(
        f"{Path(frame.filename).name}:{frame.lineno}" for frame in frames
    )
    logger.warning("%s [%s] %s", context, type(error).__name__, locations)
