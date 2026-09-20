"""只为幂等读取提供有限重试，不处理来源解析或错误文案。"""

from __future__ import annotations

import math
import time
from email.utils import parsedate_to_datetime
from http.client import HTTPException
from typing import Callable, TypeVar
from urllib.error import HTTPError

T = TypeVar("T")


def retry_delay(error: HTTPError, attempt: int, *, now: float | None = None) -> float:
    fallback = float(attempt + 1)
    raw = error.headers.get("Retry-After") if error.headers else None
    if not raw:
        return fallback
    try:
        seconds = float(raw)
    except ValueError:
        try:
            seconds = parsedate_to_datetime(raw).timestamp() - (
                time.time() if now is None else now
            )
        except (ValueError, TypeError, OverflowError):
            return fallback
    return max(0.0, min(seconds, 30.0)) if math.isfinite(seconds) else fallback


def retry_call(
    operation: Callable[[], T], *, sleep: Callable[[float], None] | None = None
) -> T:
    pause = sleep or time.sleep
    for attempt in range(3):
        try:
            return operation()
        except HTTPError as exc:
            if attempt == 2 or not (exc.code == 429 or 500 <= exc.code < 600):
                raise
            delay = retry_delay(exc, attempt)
            exc.close()
            pause(delay)
        except (OSError, HTTPException):
            if attempt == 2:
                raise
            pause(float(attempt + 1))
    raise AssertionError("unreachable")
