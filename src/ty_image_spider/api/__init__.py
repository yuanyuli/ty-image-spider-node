"""HTTP API 的稳定公开入口。"""

from .handlers import (
    execute_payload,
    get_cache_status,
    get_providers,
    post_cache_cancel,
    post_cache_start,
    post_detail,
    post_download,
    post_download_image,
    post_download_page,
    post_opencli_connect,
    post_provider_check,
    post_search,
    respond,
)
from .registration import ROUTES, register_routes
from .responses import error, safe_json, safe_text, success, unexpected_error
from .service_locator import get_services

__all__ = [
    "ROUTES",
    "error",
    "execute_payload",
    "get_cache_status",
    "get_providers",
    "get_services",
    "post_cache_cancel",
    "post_cache_start",
    "post_detail",
    "post_download",
    "post_download_image",
    "post_download_page",
    "post_opencli_connect",
    "post_provider_check",
    "post_search",
    "register_routes",
    "respond",
    "safe_json",
    "safe_text",
    "success",
    "unexpected_error",
]
