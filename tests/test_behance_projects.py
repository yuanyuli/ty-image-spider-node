import io
import json

import pytest

from ty_image_spider.models import SpiderError
from ty_image_spider.providers.behance_projects import BehanceProjects


class Response(io.BytesIO):
    def geturl(self):
        return "https://www.behance.net/v3/graphql"


@pytest.mark.parametrize("query", ["", "poster"])
def test_connection_pagination_and_search_variables(query):
    requests = []

    def open_url(request, timeout):
        requests.append(json.loads(request.data))
        variables = requests[-1]["variables"]
        connection = {
            "nodes": [{"id": 1 if variables["after"] is None else 2}],
            "pageInfo": {
                "hasNextPage": variables["after"] is None,
                "endCursor": "next",
            },
        }
        data = (
            {"search": connection} if query else {"gallery": {"projects": connection}}
        )
        return Response(json.dumps({"data": data}).encode())

    client = BehanceProjects(open_url)
    first, cursor = client.read("photography", query, None)
    second, last = client.read("photography", query, cursor)
    assert first[0]["id"] != second[0]["id"]
    assert cursor == "next"
    assert last is None
    assert requests[1]["variables"]["after"] == "next"
    assert requests[0]["variables"].get("query", "") == query


@pytest.mark.parametrize(
    "payload", [{"errors": [{"message": "failed"}]}, {"data": None}, []]
)
def test_malformed_connection_is_not_silently_empty(payload):
    client = BehanceProjects(lambda *a, **kw: Response(json.dumps(payload).encode()))
    with pytest.raises(SpiderError, match="分页数据无效"):
        client.read("photography", "", None)
