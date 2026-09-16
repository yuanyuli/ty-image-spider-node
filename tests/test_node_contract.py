from ty_image_spider.nodes import TyImageSpider


def test_node_is_zero_output_and_serializes_only_state():
    inputs = TyImageSpider.INPUT_TYPES()

    assert TyImageSpider.RETURN_TYPES == ()
    assert TyImageSpider.RETURN_NAMES == ()
    assert TyImageSpider.OUTPUT_NODE is True
    assert TyImageSpider.FUNCTION == "browse"
    assert TyImageSpider.CATEGORY == "TY Utils/素材浏览"
    assert set(inputs["required"]) == {"state_json"}
    assert inputs["required"]["state_json"][1]["hidden"] is True
    assert TyImageSpider().browse('{"provider":"local"}') == {
        "ui": {"state": ['{"provider":"local"}']}
    }


def test_node_replaces_non_string_state_with_empty_object():
    assert TyImageSpider().browse(None) == {"ui": {"state": ["{}"]}}

