"""ComfyUI 输出目录绑定的惰性应用服务定位器。"""

from __future__ import annotations

import importlib
import threading
from pathlib import Path

from ..app import ApplicationServices, build_services
from ..infrastructure.cache_paths import prepare_cache_root


_services: ApplicationServices | None = None
_services_lock = threading.Lock()


def get_services() -> ApplicationServices:
    global _services
    if _services is not None:
        return _services
    with _services_lock:
        if _services is None:
            folder_paths = importlib.import_module("folder_paths")
            output_root = Path(folder_paths.get_output_directory())
            cache_root = prepare_cache_root(output_root)
            _services = build_services(output_root, cache_root)
    return _services
