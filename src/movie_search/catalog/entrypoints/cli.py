"""The `ingest` command: translates arguments and outcomes of `ImportMovies` (RF1, RF2)."""

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

from movie_search.catalog.application import (
    CatalogUnavailable,
    ImportInterrupted,
    ImportMovies,
    ImportReport,
    SkipReason,
    SourceUnavailable,
)


def register(
    subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]",
    import_movies_factory: Callable[[], ImportMovies],
    default_path: Path | None,
) -> None:
    """Add `ingest`; the factory runs only once the arguments are known to be valid."""
    parser = subparsers.add_parser(
        "ingest", help="load an OMDb JSONL file into the catalog"
    )
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        metavar="PATH",
        help="JSONL file to read (default: MOVIES_DATA_PATH)",
    )
    parser.add_argument(
        "--limit",
        type=_positive_int,
        metavar="N",
        help="stop after storing N movies",
    )

    def run(args: argparse.Namespace) -> int:
        path = args.path or default_path
        if path is None:
            parser.error("no PATH given and MOVIES_DATA_PATH is not set")
        return _ingest(import_movies_factory, path, args.limit)

    parser.set_defaults(run=run)


def _ingest(
    import_movies_factory: Callable[[], ImportMovies], path: Path, limit: int | None
) -> int:
    try:
        report = import_movies_factory().execute(path, limit=limit)
    except (SourceUnavailable, CatalogUnavailable) as error:
        _print_error(str(error))
        return 1
    except ImportInterrupted as error:
        print(_format_report(error.report))
        _print_error(
            "import interrupted: the catalog became unavailable; "
            "movies already stored were kept and running ingest again is safe"
        )
        return 1
    print(_format_report(report))
    return 0


def _positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        number = 0
    if number < 1:
        raise argparse.ArgumentTypeError(f"{value!r} is not an integer >= 1")
    return number


def _format_report(report: ImportReport) -> str:
    totals = [
        ("Read:", report.read),
        ("Inserted:", report.inserted),
        ("Updated:", report.updated),
        ("Skipped:", sum(report.skipped.values())),
    ]
    lines = [f"{label:<10}{count:>7,}" for label, count in totals]
    lines += [
        f"  {reason:<18}{report.skipped[reason]:>4,}"
        for reason in SkipReason
        if report.skipped.get(reason)
    ]
    return "\n".join(lines)


def _print_error(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
