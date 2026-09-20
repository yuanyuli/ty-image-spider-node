import json
from io import BytesIO

import pytest

from ty_image_spider.models import SpiderError
from ty_image_spider.movies.tmdb import TmdbClient, TmdbCredentials


class Response(BytesIO):
    headers = {}

    def geturl(self):
        return "https://api.themoviedb.org/3/search/movie"


def test_token_is_sent_only_in_header_and_search_is_chinese(tmp_path):
    credentials = TmdbCredentials(
        tmp_path / "tmdb.json", environment={"TMDB_READ_ACCESS_TOKEN": "private-token"}
    )

    def open_url(request, timeout):
        assert request.get_header("Authorization") == "Bearer private-token"
        assert "private-token" not in request.full_url
        assert "language=zh-CN" in request.full_url
        return Response(
            json.dumps(
                {
                    "results": [
                        {
                            "id": 680,
                            "title": "低俗小说",
                            "release_date": "1994-09-10",
                            "poster_path": "/poster.jpg",
                        }
                    ]
                }
            ).encode()
        )

    result = TmdbClient(credentials, open_url=open_url).search("低俗小说")
    assert result[0]["year"] == 1994
    assert result[0]["title"] == "低俗小说"


def test_missing_token_is_actionable_and_file_changes_are_read_without_restart(
    tmp_path,
):
    path = tmp_path / "tmdb.json"
    credentials = TmdbCredentials(path, environment={})
    with pytest.raises(SpiderError, match="读取令牌"):
        TmdbClient(credentials).search("低俗小说")
    path.write_text('{"read_access_token":"example"}')
    assert credentials.read() == "example"
