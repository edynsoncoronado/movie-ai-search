"""RF2 and RF3: `parse_line` over the lines in tests/fixtures/omdb_edge_cases.jsonl.

Each fixture line carries a `"case"` label (also in the lines that are not valid
JSON), so tests look lines up by name instead of by line number.
"""

import json
import re
from pathlib import Path

import pytest

from movie_search.catalog.domain.models import (
    Movie,
    SkippedRecord,
    SkipReason,
    SourceLine,
)
from movie_search.catalog.domain.parsing import parse_line

FIXTURE = Path(__file__).parents[2] / "fixtures" / "omdb_edge_cases.jsonl"
CASE_LABEL = re.compile(r'"case"\s*:\s*"([^"]+)"')


def _load_cases() -> dict[str, SourceLine]:
    cases: dict[str, SourceLine] = {}
    lines = FIXTURE.read_text(encoding="utf-8").splitlines()
    for number, text in enumerate(lines, start=1):
        match = CASE_LABEL.search(text)
        assert match, f"fixture line {number} has no case label"
        label = match.group(1)
        assert label not in cases, f"duplicate case label {label!r}"
        cases[label] = SourceLine(line_number=number, text=text)
    return cases


CASES = _load_cases()


def _skip(case: str) -> SkippedRecord:
    result = parse_line(CASES[case])
    assert isinstance(result, SkippedRecord), f"{case}: expected a skip, got {result!r}"
    assert result.line_number == CASES[case].line_number
    return result


def _movie(case: str) -> Movie:
    result = parse_line(CASES[case])
    assert isinstance(result, Movie), f"{case}: expected a movie, got {result!r}"
    return result


# --- RF2: one test per skip reason -------------------------------------------


@pytest.mark.parametrize("case", ["bad_json_truncated", "bad_json_trailing_comma"])
def test_rf2_invalid_record_bad_json(case: str) -> None:
    assert _skip(case) == SkippedRecord(
        line_number=CASES[case].line_number,
        imdb_id=None,
        reason=SkipReason.INVALID_RECORD,
    )


@pytest.mark.parametrize(
    "case", ["top_level_array", "raw_missing", "raw_string", "raw_null", "raw_list"]
)
def test_rf2_invalid_record_raw_not_object(case: str) -> None:
    assert _skip(case).reason is SkipReason.INVALID_RECORD


def test_rf2_invalid_record_not_utf8() -> None:
    result = parse_line(SourceLine(line_number=7, text=None))

    assert result == SkippedRecord(
        line_number=7, imdb_id=None, reason=SkipReason.INVALID_RECORD
    )


@pytest.mark.parametrize(
    "case",
    ["imdb_id_missing", "imdb_id_null", "imdb_id_empty", "imdb_id_too_short"],
)
def test_rf2_missing_imdb_id(case: str) -> None:
    assert _skip(case).reason is SkipReason.MISSING_IMDB_ID


def test_rf2_invalid_response() -> None:
    assert _skip("invalid_response") == SkippedRecord(
        line_number=CASES["invalid_response"].line_number,
        imdb_id="tt0000011",
        reason=SkipReason.INVALID_RESPONSE,
    )


@pytest.mark.parametrize(
    ("case", "imdb_id"), [("type_episode", "tt0000012"), ("type_series", "tt0000013")]
)
def test_rf2_not_a_movie(case: str, imdb_id: str) -> None:
    assert _skip(case) == SkippedRecord(
        line_number=CASES[case].line_number,
        imdb_id=imdb_id,
        reason=SkipReason.NOT_A_MOVIE,
    )


@pytest.mark.parametrize(
    "case", ["title_missing", "title_empty", "title_na", "title_blank"]
)
def test_rf2_missing_title(case: str) -> None:
    result = _skip(case)

    assert result.reason is SkipReason.MISSING_TITLE
    assert result.imdb_id is not None and result.imdb_id.startswith("tt")


@pytest.mark.parametrize(
    "case", ["plot_missing", "plot_empty", "plot_na", "plot_blank"]
)
def test_rf2_missing_plot(case: str) -> None:
    result = _skip(case)

    assert result.reason is SkipReason.MISSING_PLOT
    assert result.imdb_id is not None and result.imdb_id.startswith("tt")


# --- RF2: precedence and identity --------------------------------------------


@pytest.mark.parametrize(
    ("case", "reason"),
    [
        ("response_false_no_plot", SkipReason.INVALID_RESPONSE),
        ("bad_imdb_id_response_false", SkipReason.MISSING_IMDB_ID),
    ],
)
def test_rf2_precedence(case: str, reason: SkipReason) -> None:
    assert _skip(case).reason is reason


def test_rf2_uses_top_level_imdb_id_and_ignores_raw_imdbID() -> None:
    assert _movie("top_level_id_wins").imdb_id == "tt0000023"
    assert _skip("raw_id_only").reason is SkipReason.MISSING_IMDB_ID


# --- RF3: normalization through parse_line -----------------------------------


def test_rf3_full_sample_record_maps_every_field() -> None:
    raw = json.loads(CASES["full_sample_record"].text or "")["raw"]

    assert _movie("full_sample_record") == Movie(
        imdb_id="tt0032145",
        title="Wuthering Heights",
        year=1939,
        plot=raw["Plot"],
        genres=("Drama", "Romance"),
        directors=("William Wyler",),
        writers=("Charles MacArthur", "Ben Hecht", "Emily Brontë"),
        actors=("Merle Oberon", "Laurence Olivier", "David Niven"),
        languages=("English",),
        countries=("United States",),
        runtime_min=104,
        imdb_votes=20678,
        imdb_rating=7.5,
        rated="Approved",
        awards="Won 1 Oscar. 9 wins & 7 nominations total",
        poster_url=raw["Poster"],
    )


def test_rf3_sparse_record_trimmed_and_missing_fields_empty() -> None:
    # N/A, empty, blank and absent keys -> None / (); strings trimmed (RF2, RF3).
    assert _movie("sparse_record") == Movie(
        imdb_id="tt0000030",
        title="Sparse Movie",
        year=None,
        plot="A plot.",
        genres=(),
        directors=(),
        writers=(),
        actors=(),
        languages=("English",),
        countries=(),
        runtime_min=None,
        imdb_votes=None,
        imdb_rating=None,
        rated="PG-13",
        awards=None,
        poster_url=None,
    )
