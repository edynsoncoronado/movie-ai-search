"""RF3: the pure field parsers, table-driven."""

from collections.abc import Callable

import pytest

from movie_search.catalog.domain.parsing import (
    parse_float,
    parse_int,
    parse_languages,
    parse_minutes,
    parse_year,
    split_list,
)

SCALAR_PARSERS: list[Callable[[str | None], object]] = [
    parse_year,
    parse_minutes,
    parse_int,
    parse_float,
]
LIST_PARSERS: list[Callable[[str | None], tuple[str, ...]]] = [
    split_list,
    parse_languages,
]
MISSING_VALUES = [None, "N/A", "  N/A  ", "", "  "]


@pytest.mark.parametrize("value", MISSING_VALUES)
@pytest.mark.parametrize("parser", SCALAR_PARSERS, ids=lambda p: p.__name__)
def test_rf3_na_and_empty_are_missing_scalars(
    parser: Callable[[str | None], object], value: str | None
) -> None:
    assert parser(value) is None


@pytest.mark.parametrize("value", MISSING_VALUES)
@pytest.mark.parametrize("parser", LIST_PARSERS, ids=lambda p: p.__name__)
def test_rf3_na_and_empty_are_missing_lists(
    parser: Callable[[str | None], tuple[str, ...]], value: str | None
) -> None:
    assert parser(value) == ()


@pytest.mark.parametrize(
    ("parser", "value", "expected"),
    [
        (split_list, "  x  ", ("x",)),
        (parse_languages, "  English  ", ("English",)),
        (parse_year, "  1994  ", 1994),
        (parse_minutes, "  104 min  ", 104),
        (parse_int, "  20,678  ", 20678),
        (parse_float, "  7.8  ", 7.8),
    ],
    ids=lambda v: v.__name__ if callable(v) else None,
)
def test_rf3_strings_are_trimmed(
    parser: Callable[[str | None], object], value: str, expected: object
) -> None:
    assert parser(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1994", 1994),
        ("2025–", 2025),
        ("c. 1999", None),
        ("abc", None),
        ("199", None),
    ],
)
def test_rf3_year_first_four_digits(value: str, expected: int | None) -> None:
    assert parse_year(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("104 min", 104),
        ("7 min", 7),
        ("abc", None),
        ("min", None),
    ],
)
def test_rf3_runtime_minutes(value: str, expected: int | None) -> None:
    assert parse_minutes(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("20,678", 20678),
        ("1,234,567", 1234567),
        ("7817", 7817),
        ("abc", None),
    ],
)
def test_rf3_votes_with_thousands_separator(value: str, expected: int | None) -> None:
    assert parse_int(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("7.8", 7.8),
        ("10.0", 10.0),
        ("abc", None),
    ],
)
def test_rf3_rating_float(value: str, expected: float | None) -> None:
    result = parse_float(value)
    if expected is None:
        assert result is None
    else:
        assert result == pytest.approx(expected)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Drama", ("Drama",)),
        ("Drama, Romance", ("Drama", "Romance")),
        ("  Drama ,Romance  ,  War ", ("Drama", "Romance", "War")),
        ("Drama,, Romance, ", ("Drama", "Romance")),
        (" , ", ()),
    ],
)
def test_rf3_lists_split_trimmed_and_drop_empty(
    value: str, expected: tuple[str, ...]
) -> None:
    assert split_list(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("None", ()),
        ("None, English", ("English",)),
        ("English, None", ("English",)),
        ("English, French", ("English", "French")),
    ],
)
def test_rf3_language_drops_none(value: str, expected: tuple[str, ...]) -> None:
    assert parse_languages(value) == expected
