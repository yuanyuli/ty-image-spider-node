"""保存详情中的指定单张，复用来源校验和既有落盘策略。"""

from pathlib import Path

from ..models import AssetItem, DownloadResult, SpiderError
from ..providers.base import AssetProvider
from ..providers.curated_download import CuratedDownloader


def download_selected_image(
    provider: AssetProvider, item: AssetItem, image_index: object, output_root: Path
) -> DownloadResult:
    if type(image_index) is not int or image_index < 0:
        raise SpiderError("invalid_image_index", "图片序号无效")
    if not provider.descriptor().capabilities.download:
        raise SpiderError("download_unsupported", "当前素材无需或不支持下载")
    images = provider.detail(item).images
    if image_index >= len(images):
        raise SpiderError("invalid_image_index", "图片序号已失效，请重新打开详情")
    # 单图保留来源专属处理（如 Civitai 的 PNG 提示词），不另造下载逻辑。
    if len(images) == 1 and item.download_mode != "gallery":
        return provider.download(item, output_root)
    policy = provider.image_policy
    if policy is None:
        raise SpiderError("download_unsupported", "当前素材源不支持单张保存")
    return CuratedDownloader(policy).download(
        images[image_index], f"{item.id}-{image_index + 1}", output_root
    )
