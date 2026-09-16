from PIL import Image, PngImagePlugin

from ty_image_spider.metadata import extract_prompts, read_image_metadata


def test_workflow_json_is_not_treated_as_prompt():
    prompt, negative = extract_prompts({"prompt": '{"nodes":[{"id":1}]}'})

    assert prompt == ""
    assert negative == ""


def test_extract_prompts_supports_common_string_fields():
    assert extract_prompts({"positivePrompt": "cat", "negative_prompt": "blur"}) == (
        "cat",
        "blur",
    )


def test_read_image_metadata_reads_png_text_and_returns_json_safe_values(tmp_path):
    path = tmp_path / "sample.png"
    info = PngImagePlugin.PngInfo()
    info.add_text("prompt", "mountain at dawn")
    info.add_text("workflow", '{"nodes":[]}')
    Image.new("RGB", (4, 3), (10, 20, 30)).save(path, pnginfo=info)

    metadata = read_image_metadata(path)

    assert metadata["prompt"] == "mountain at dawn"
    assert metadata["workflow"] == '{"nodes":[]}'
    assert metadata["width"] == 4
    assert metadata["height"] == 3


def test_read_image_metadata_returns_empty_for_non_image(tmp_path):
    path = tmp_path / "not-image.txt"
    path.write_text("hello", encoding="utf-8")

    assert read_image_metadata(path) == {}
