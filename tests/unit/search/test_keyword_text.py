"""RF6: the keyword text a movie is indexed by."""

import pytest

from movie_search.search.domain.keyword_text import keyword_text
from movie_search.search.domain.models import IndexableMovie

PLOT = "A blade runner must pursue and terminate four replicants."


def _movie(**overrides: object) -> IndexableMovie:
    fields: dict[str, object] = {
        "imdb_id": "tt0083658",
        "title": "Blade Runner",
        "directors": ("Ridley Scott",),
        "actors": ("Harrison Ford", "Rutger Hauer", "Sean Young"),
        "genres": ("Action", "Drama", "Sci-Fi"),
        "plot": PLOT,
    }
    return IndexableMovie(**(fields | overrides))  # type: ignore[arg-type]


def test_rf6_title_written_twice() -> None:
    lines = keyword_text(_movie()).split("\n")

    assert lines[:2] == ["Blade Runner", "Blade Runner"]
    assert lines.count("Blade Runner") == 2


def test_rf6_parts_in_order_title_directors_actors_genres_plot() -> None:
    assert keyword_text(_movie()).split("\n") == [
        "Blade Runner",
        "Blade Runner",
        "Ridley Scott",
        "Harrison Ford, Rutger Hauer, Sean Young",
        "Action, Drama, Sci-Fi",
        PLOT,
    ]


@pytest.mark.parametrize(
    ("overrides", "expected_lines"),
    [
        (
            {"directors": ()},
            [
                "T",
                "T",
                "Harrison Ford, Rutger Hauer, Sean Young",
                "Action, Drama, Sci-Fi",
                PLOT,
            ],
        ),
        (
            {"actors": ()},
            ["T", "T", "Ridley Scott", "Action, Drama, Sci-Fi", PLOT],
        ),
        (
            {"genres": ()},
            ["T", "T", "Ridley Scott", "Harrison Ford, Rutger Hauer, Sean Young", PLOT],
        ),
        (
            {"directors": (), "actors": (), "genres": ()},
            ["T", "T", PLOT],
        ),
        (
            {"directors": (), "actors": (), "genres": (), "plot": ""},
            ["T", "T"],
        ),
    ],
    ids=["no-directors", "no-actors", "no-genres", "title-and-plot", "title-only"],
)
def test_rf6_missing_parts_left_out(
    overrides: dict[str, object], expected_lines: list[str]
) -> None:
    text = keyword_text(_movie(title="T", **overrides))

    assert text == "\n".join(expected_lines)
