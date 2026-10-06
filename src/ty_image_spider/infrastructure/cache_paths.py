"""只负责资料缓存目录定位及旧目录迁移，不构造服务或读取缓存内容。"""

from pathlib import Path


def prepare_cache_root(output_root: Path) -> Path:
    """在服务首次初始化前迁移旧目录；已有新目录不被覆盖。"""
    target = output_root / "ty-node" / "ty-image-spider" / ".cache"
    legacy = output_root / "ty-image-spider" / ".cache"
    if legacy.is_dir() and not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        legacy.rename(target)
    return target
