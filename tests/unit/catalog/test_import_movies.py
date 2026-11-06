"""RF1, RF2, RF4: `ImportMovies` over the in-memory source and repository."""

import json
import logging
from collections.abc import Iterable, Mapping
from pathlib import Path

import pytest

from movie_search.catalog.application import (
    ImportInterrupted,
    ImportMovies,
    ImportReport,
    Movie,
    SkipReason,
    SourceUnavailable,
)
from tests.fakes.catalog import InMemoryMovieRepository, InMemoryMovieSource

PATH = Path("movies.jsonl")
BAD_JSON = '{"imdb_id": "tt0000099", "raw": {'


def _line(imdb_id: str | None, **raw: str) -> str:
    """A valid record, unless `imdb_id` or the `raw` overrides make it invalid."""
    fields = {
        "Response": "True",
        "Type": "movie",
        "Title": f"Title of {imdb_id}",
        "Plot": "A plot.",
    }
    return json.dumps({"imdb_id": imdb_id, "raw": fields | raw})


def _ids(count: int) -> list[str]:
    return [f"tt{number:07d}" for number in range(1, count + 1)]


def _import(
    lines: Iterable[str | None],
    repository: InMemoryMovieRepository,
    limit: int | None = None,
) -> ImportReport:
    source = InMemoryMovieSource(lines)
    return ImportMovies(source, repository).execute(PATH, limit=limit)


def _stored_ids(repository: InMemoryMovieRepository) -> list[str]:
    return [movie.imdb_id for movie in repository.iter_all()]


def _nonzero(skipped: Mapping[SkipReason, int]) -> dict[SkipReason, int]:
    """Whether reasons with no skips appear in the report is not part of the contract."""
    return {reason: count for reason, count in skipped.items() if count}


def _warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]


# --- Counts and skips ---------------------------------------------------------


def test_rf2_report_counts_per_reason() -> None:
    lines = [
        _line("tt0000001"),
        BAD_JSON,
        None,  # not UTF-8: a non-blank line, so it is read and skipped
        _line(None),
        _line("tt0000002", Response="False"),
        _line("tt0000003", Response="False"),
        _line("tt0000004", Response="False"),
        _line("tt0000005", Type="series"),
        _line("tt0000006", Title="N/A"),
        _line("tt0000007", Plot="N/A"),
        _line("tt0000008", Plot=""),
        _line("tt0000009"),
    ]

    report = _import(lines, InMemoryMovieRepository())

    assert report.read == 12
    assert report.inserted == 2
    assert report.updated == 0
    assert _nonzero(report.skipped) == {
        SkipReason.INVALID_RECORD: 2,
        SkipReason.MISSING_IMDB_ID: 1,
        SkipReason.INVALID_RESPONSE: 3,
        SkipReason.NOT_A_MOVIE: 1,
        SkipReason.MISSING_TITLE: 1,
        SkipReason.MISSING_PLOT: 2,
    }


def test_rf2_warning_logged_per_skip(caplog: pytest.LogCaptureFixture) -> None:
    lines = [
        _line("tt0000001"),
        BAD_JSON,
        _line("tt0000002", Response="False"),
        _line("tt0000003"),
    ]

    with caplog.at_level(logging.WARNING):
        _import(lines, InMemoryMovieRepository())

    assert _warnings(caplog) == [
        "skipped line=2 imdb_id=- reason=invalid_record",
        "skipped line=3 imdb_id=tt0000002 reason=invalid_response",
    ]


def test_rf1_blank_lines_neither_read_nor_skipped(
    caplog: pytest.LogCaptureFixture,
) -> None:
    lines = ["", _line("tt0000001"), "   ", "\n", _line("tt0000002"), "\t\n"]

    with caplog.at_level(logging.WARNING):
        report = _import(lines, InMemoryMovieRepository())

    assert report.read == 2
    assert report.inserted == 2
    assert _nonzero(report.skipped) == {}
    assert _warnings(caplog) == []


# --- Limit --------------------------------------------------------------------


def test_rf1_limit_counts_inserted_and_updated() -> None:
    repository = InMemoryMovieRepository(
        [Movie(imdb_id="tt0000001", title="Old title", plot="Old plot.")]
    )
    lines = [
        _line("tt0000001"),  # updated: already in the catalog
        _line("tt0000002"),  # inserted
        _line("tt0000002"),  # updated: earlier in the same file
        _line("tt0000003"),  # over the limit
    ]

    report = _import(lines, repository, limit=3)

    assert report.inserted == 1
    assert report.updated == 2
    assert _stored_ids(repository) == ["tt0000001", "tt0000002"]


def test_rf1_limit_3_stores_exactly_3() -> None:
    repository = InMemoryMovieRepository()
    # Skipped records do not count toward the limit.
    lines = [
        _line("tt0000001"),
        BAD_JSON,
        _line("tt0000002"),
        _line("tt0000099", Plot="N/A"),
        _line("tt0000003"),
        _line("tt0000004"),
        _line("tt0000005"),
    ]

    report = _import(lines, repository, limit=3)

    assert report.inserted == 3
    assert report.updated == 0
    assert _stored_ids(repository) == ["tt0000001", "tt0000002", "tt0000003"]


def test_rf1_limit_spanning_two_batches_stores_exact_total() -> None:
    repository = InMemoryMovieRepository()
    ids = _ids(1200)

    report = _import([_line(imdb_id) for imdb_id in ids], repository, limit=700)

    assert report.inserted == 700
    assert _stored_ids(repository) == ids[:700]
    assert [len(batch) for batch in repository.batches] == [500, 200]


# --- Upsert -------------------------------------------------------------------


def test_rf4_last_record_wins_within_file() -> None:
    repository = InMemoryMovieRepository()
    lines = [
        _line("tt0000001", Title="First"),
        _line("tt0000002"),
        _line("tt0000001", Title="Last"),
    ]

    report = _import(lines, repository)

    assert report.inserted == 2
    assert report.updated == 1
    assert _stored_ids(repository) == ["tt0000001", "tt0000002"]
    assert repository.get_many(["tt0000001"])["tt0000001"].title == "Last"


def test_rf4_reimport_counts_updated() -> None:
    repository = InMemoryMovieRepository()
    lines = [_line(imdb_id) for imdb_id in _ids(3)]

    first = _import(lines, repository)
    second = _import(lines, repository)

    assert (first.inserted, first.updated) == (3, 0)
    assert (second.inserted, second.updated) == (0, 3)
    assert _stored_ids(repository) == _ids(3)


# --- Errors -------------------------------------------------------------------


def test_rf1_source_unavailable_writes_nothing() -> None:
    repository = InMemoryMovieRepository()
    source = InMemoryMovieSource([_line("tt0000001")], unavailable=True)

    with pytest.raises(SourceUnavailable):
        ImportMovies(source, repository).execute(PATH)

    assert repository.batches == []


def test_rf1_catalog_failure_on_batch_1_raises_import_interrupted_with_zero_counts() -> (
    None
):
    repository = InMemoryMovieRepository(fail_after_batches=0)
    lines = [_line("tt0000001"), BAD_JSON, _line("tt0000002")]

    with pytest.raises(ImportInterrupted) as interrupted:
        _import(lines, repository)

    report = interrupted.value.report
    assert (report.read, report.inserted, report.updated) == (3, 0, 0)
    assert _nonzero(report.skipped) == {SkipReason.INVALID_RECORD: 1}
    assert _stored_ids(repository) == []


def test_rf1_catalog_failure_on_batch_2_raises_import_interrupted_with_batch_1_counts() -> (
    None
):
    ids = _ids(700)
    # 10 of the 500 movies in batch 1 already exist, so it has both kinds of count.
    existing = [Movie(imdb_id=i, title="Old title", plot="Old.") for i in ids[:10]]
    repository = InMemoryMovieRepository(existing, fail_after_batches=1)

    with pytest.raises(ImportInterrupted) as interrupted:
        _import([_line(imdb_id) for imdb_id in ids], repository)

    report = interrupted.value.report
    assert (report.read, report.inserted, report.updated) == (700, 490, 10)
    assert _stored_ids(repository) == ids[:500]
