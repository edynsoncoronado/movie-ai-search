"""RF1, RF2: the `ingest` command, with an autospec of `ImportMovies`."""

import argparse
from collections.abc import Callable, Sequence
from pathlib import Path
from unittest.mock import NonCallableMagicMock, create_autospec

import pytest

from movie_search.catalog.application import (
    CatalogUnavailable,
    ImportInterrupted,
    ImportMovies,
    ImportReport,
    SkipReason,
    SourceUnavailable,
)
from movie_search.catalog.entrypoints.cli import register

EXPLICIT_PATH = Path("explicit.jsonl")
DEFAULT_PATH = Path("default.jsonl")
REPORT = ImportReport(read=3, inserted=2, updated=1, skipped={})
EMPTY_REPORT_TEXT = """\
Read:           3
Inserted:       2
Updated:        1
Skipped:        0
"""


@pytest.fixture
def import_movies() -> NonCallableMagicMock:
    use_case = create_autospec(ImportMovies, instance=True)
    use_case.execute.return_value = REPORT
    return use_case


def _run(
    argv: Sequence[str],
    factory: Callable[[], ImportMovies],
    default_path: Path | None = None,
) -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(required=True)
    register(subparsers, factory, default_path)
    args = parser.parse_args(["ingest", *argv])
    return args.run(args)


def _factory_must_not_run() -> ImportMovies:
    raise AssertionError("a usage error must not build the use case")


def test_rf1_ingest_explicit_path(
    import_movies: NonCallableMagicMock, capsys: pytest.CaptureFixture[str]
) -> None:
    code = _run([str(EXPLICIT_PATH)], lambda: import_movies, DEFAULT_PATH)

    assert code == 0
    import_movies.execute.assert_called_once_with(EXPLICIT_PATH, limit=None)
    assert capsys.readouterr().out == EMPTY_REPORT_TEXT


def test_rf1_ingest_default_path_from_settings(
    import_movies: NonCallableMagicMock,
) -> None:
    code = _run([], lambda: import_movies, DEFAULT_PATH)

    assert code == 0
    import_movies.execute.assert_called_once_with(DEFAULT_PATH, limit=None)


def test_rf1_ingest_limit_reaches_the_use_case(
    import_movies: NonCallableMagicMock,
) -> None:
    code = _run([str(EXPLICIT_PATH), "--limit", "3"], lambda: import_movies)

    assert code == 0
    import_movies.execute.assert_called_once_with(EXPLICIT_PATH, limit=3)


def test_rf1_ingest_no_path_no_env_exit_2(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        _run([], _factory_must_not_run, default_path=None)

    assert exit_info.value.code == 2
    assert "MOVIES_DATA_PATH" in capsys.readouterr().err


@pytest.mark.parametrize("limit", ["0", "-1", "abc"])
def test_rf1_ingest_bad_limit_exit_2(
    limit: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exit_info:
        _run([str(EXPLICIT_PATH), "--limit", limit], _factory_must_not_run)

    assert exit_info.value.code == 2
    assert "--limit" in capsys.readouterr().err


def test_rf1_ingest_source_unavailable_exit_1(
    import_movies: NonCallableMagicMock, capsys: pytest.CaptureFixture[str]
) -> None:
    import_movies.execute.side_effect = SourceUnavailable("cannot read explicit.jsonl")

    code = _run([str(EXPLICIT_PATH)], lambda: import_movies)

    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    assert captured.err == "error: cannot read explicit.jsonl\n"


def test_rf1_ingest_schema_failure_one_line_error_no_report_exit_1(
    capsys: pytest.CaptureFixture[str],
) -> None:
    def factory() -> ImportMovies:
        raise CatalogUnavailable("the catalog database is unavailable")

    code = _run([str(EXPLICIT_PATH)], factory)

    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    assert captured.err == "error: the catalog database is unavailable\n"


def test_rf1_ingest_interrupted_prints_partial_report_exit_1(
    import_movies: NonCallableMagicMock, capsys: pytest.CaptureFixture[str]
) -> None:
    import_movies.execute.side_effect = ImportInterrupted(REPORT)

    code = _run([str(EXPLICIT_PATH)], lambda: import_movies)

    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == EMPTY_REPORT_TEXT
    assert captured.err.startswith("error: import interrupted")
    assert captured.err.count("\n") == 1


def test_rf2_ingest_report_format(
    import_movies: NonCallableMagicMock, capsys: pytest.CaptureFixture[str]
) -> None:
    # Out of RF2 order and with a zero, to show the report sorts and drops them.
    import_movies.execute.return_value = ImportReport(
        read=47_203,
        inserted=46_963,
        updated=0,
        skipped={
            SkipReason.MISSING_PLOT: 209,
            SkipReason.MISSING_TITLE: 0,
            SkipReason.NOT_A_MOVIE: 3,
            SkipReason.INVALID_RESPONSE: 28,
        },
    )

    _run([str(EXPLICIT_PATH)], lambda: import_movies)

    assert (
        capsys.readouterr().out
        == """\
Read:      47,203
Inserted:  46,963
Updated:        0
Skipped:      240
  invalid_response    28
  not_a_movie          3
  missing_plot       209
"""
    )
