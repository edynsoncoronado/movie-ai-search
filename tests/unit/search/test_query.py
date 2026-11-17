"""RF7, RF8: `SearchQuery` trims and validates the text and the limit."""

import pytest

from movie_search.search.domain.query import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    MAX_QUERY_LENGTH,
    InvalidSearchQuery,
    SearchQuery,
)


def test_rf7_query_trimmed() -> None:
    assert SearchQuery("  \t blade runner \n ").text == "blade runner"


@pytest.mark.parametrize("text", ["", " ", "   ", "\t\n "])
def test_rf8_empty_or_blank_query_rejected(text: str) -> None:
    with pytest.raises(InvalidSearchQuery):
        SearchQuery(text)


def test_rf8_query_500_ok_501_rejected() -> None:
    assert MAX_QUERY_LENGTH == 500
    longest = "a" * MAX_QUERY_LENGTH

    # The length is counted after trimming, in characters (not bytes).
    assert SearchQuery(f"  {longest}  ").text == longest
    assert SearchQuery("é" * MAX_QUERY_LENGTH).text == "é" * MAX_QUERY_LENGTH
    with pytest.raises(InvalidSearchQuery):
        SearchQuery("a" * (MAX_QUERY_LENGTH + 1))


@pytest.mark.parametrize("limit", [1, MAX_LIMIT])
def test_rf8_limit_bounds_accepted(limit: int) -> None:
    assert MAX_LIMIT == 50
    assert SearchQuery("coco", limit).limit == limit


@pytest.mark.parametrize("limit", [0, MAX_LIMIT + 1])
def test_rf8_limit_bounds_rejected(limit: int) -> None:
    with pytest.raises(InvalidSearchQuery):
        SearchQuery("coco", limit)


def test_rf7_default_limit_10() -> None:
    assert DEFAULT_LIMIT == 10
    assert SearchQuery("coco").limit == DEFAULT_LIMIT
