"""Use case: import movies from a source file into the catalog (RF1, RF2, RF4)."""

import logging
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from movie_search.catalog.application.ports import MovieRepository, MovieSource
from movie_search.catalog.domain.errors import CatalogUnavailable
from movie_search.catalog.domain.models import (
    Movie,
    SkippedRecord,
    SkipReason,
    SourceLine,
)
from movie_search.catalog.domain.parsing import parse_line

_BATCH_SIZE = 500

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ImportReport:
    """`read` counts non-blank lines; reasons with no skips are absent from `skipped`."""

    read: int
    inserted: int
    updated: int
    skipped: Mapping[SkipReason, int]


class ImportInterrupted(Exception):
    """The catalog failed during an import; `report` holds the counts so far."""

    def __init__(self, report: ImportReport) -> None:
        super().__init__(f"import interrupted: {report}")
        self.report = report


@dataclass(slots=True)
class _Tally:
    read: int = 0
    inserted: int = 0
    updated: int = 0
    skipped: Counter[SkipReason] = field(default_factory=Counter)

    @property
    def stored(self) -> int:
        return self.inserted + self.updated

    def report(self) -> ImportReport:
        return ImportReport(self.read, self.inserted, self.updated, dict(self.skipped))


class ImportMovies:
    def __init__(self, source: MovieSource, repository: MovieRepository) -> None:
        self._source = source
        self._repository = repository

    def execute(self, path: Path, limit: int | None = None) -> ImportReport:
        """Upsert the file's valid movies in batches, up to `limit` stored movies.

        Reading stops at the movie that reaches `limit`, so later lines are neither
        read nor skipped. Raises SourceUnavailable if the file cannot be read, and
        ImportInterrupted if the catalog fails; batches already stored remain.
        """
        tally = _Tally()
        batch: list[Movie] = []
        for line in self._source.open(path):
            if _is_blank(line):
                continue
            tally.read += 1
            parsed = parse_line(line)
            if isinstance(parsed, SkippedRecord):
                _record_skip(parsed, tally)
                continue
            batch.append(parsed)
            if len(batch) == _next_batch_size(tally, limit):
                self._store(batch, tally)
                batch = []
                if tally.stored == limit:
                    break
        if batch:
            self._store(batch, tally)
        return tally.report()

    def _store(self, batch: list[Movie], tally: _Tally) -> None:
        try:
            result = self._repository.upsert_many(batch)
        except CatalogUnavailable as error:
            raise ImportInterrupted(tally.report()) from error
        tally.inserted += result.inserted
        tally.updated += result.updated


def _is_blank(line: SourceLine) -> bool:
    # text=None is a line that is not UTF-8: it has content, so it is not blank.
    return line.text is not None and not line.text.strip()


def _record_skip(record: SkippedRecord, tally: _Tally) -> None:
    tally.skipped[record.reason] += 1
    logger.warning(
        "skipped line=%d imdb_id=%s reason=%s",
        record.line_number,
        record.imdb_id or "-",
        record.reason,
    )


def _next_batch_size(tally: _Tally, limit: int | None) -> int:
    if limit is None:
        return _BATCH_SIZE
    return min(_BATCH_SIZE, limit - tally.stored)
