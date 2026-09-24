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
    ):
        assert required in text
