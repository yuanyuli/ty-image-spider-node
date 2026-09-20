"""缓存预览读取器的轻量注册表，不理解来源的下载规则。"""

from typing import Protocol

from ..models import SpiderError


class ImageReader(Protocol):
    def read(self, url: str) -> tuple[bytes, str]: ...


class ImageReaderRegistry:
    def __init__(self) -> None:
        self._readers: dict[str, ImageReader] = {}

    def register(self, provider_id: str, reader: ImageReader) -> None:
        if provider_id in self._readers:
            raise ValueError(f"图片读取器重复：{provider_id}")
        self._readers[provider_id] = reader

    def read(self, url: str, provider_id: str) -> tuple[bytes, str]:
        reader = self._readers.get(provider_id)
        if reader is None:
            raise SpiderError("invalid_provider", "不支持此来源的图片读取")
        return reader.read(url)
