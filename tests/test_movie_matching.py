from ty_image_spider.movies.matching import match_movies


def test_remakes_match_title_and_release_year_not_post_date():
    movie = {
        "title": "沙丘",
        "english_title": "Dune",
        "original_title": "Dune",
        "year": 2021,
        "directors": ["Denis Villeneuve"],
    }
    posts = [
        {"id": 1, "title": "Dune", "year": 1984, "directors": ["David Lynch"]},
        {
            "id": 2,
            "title": "Dune (2021)",
            "year": 2021,
            "directors": ["Denis Villeneuve"],
        },
        {"id": 3, "title": "Woman in the Dunes", "year": 1964},
    ]
    matches = match_movies(movie, posts)
    assert [item["id"] for item in matches] == [2, 1]
    assert matches[0]["verified"] is True
    assert matches[1]["verified"] is False


def test_missing_year_or_conflicting_director_never_auto_matches():
    movie = {"english_title": "Crash", "year": 2004, "directors": ["Paul Haggis"]}
    posts = [
        {"id": 1, "title": "Crash"},
        {"id": 2, "title": "Crash", "year": 2004, "directors": ["David Cronenberg"]},
    ]
    assert all(not item["verified"] for item in match_movies(movie, posts))
