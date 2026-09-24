from pathlib import Path


def test_readme_documents_required_install_and_privacy_boundaries():
    text = Path("README.md").read_text(encoding="utf-8")
    for required in (
        "TY Image Spider",
        "civitai.com",
        "civitai.red",
        "小红书",
        "OpenCLI >= 1.8.8",
        "Chrome 扩展",
        "output/ty-image-spider",
        "不会写入工作流",
        "CONTRIBUTING.md",
        "故障排查",
        "Prelinger Archives",
        "Wikimedia Commons 视频",
        "NASA 视频",
        "视频缓存只保存封面和资料",
    ):
        assert required in text


def test_video_source_guide_documents_runtime_and_rights_boundaries():
    text = Path("docs/sources/video.md").read_text(encoding="utf-8")
    for required in (
        "Prelinger Archives",
        "Wikimedia Commons 视频",
        "NASA 视频",
        "视频缓存只保存封面和资料",
        "2 GiB",
        "MP4",
        "WebM",
        "Ogg",
        "无需 API Key",
        "不支持整页批量下载",
        "逐项核对",
    ):
        assert required in text
