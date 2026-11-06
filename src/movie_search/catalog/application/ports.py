"""Ports of the catalog module: the I/O that `catalog.application` depends on."""

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from movie_search.catalog.domain.models import Movie, SourceLine


@dataclass(frozen=True, slots=True)
class UpsertResult:
    inserted: int
    updated: int


class MovieSource(Protocol):
    def open(self, path: Path) -> Iterator[SourceLine]:
        """Yield the file's lines; raises SourceUnavailable before yielding any."""
        ...


class MovieRepository(Protocol):
    """All methods raise CatalogUnavailable when the storage cannot be reached."""

    def upsert_many(self, movies: Sequence[Movie]) -> UpsertResult: ...

    def iter_all(self) -> Iterator[Movie]:
        """Stream every movie, ordered by imdb_id."""
        ...

    def get_many(self, imdb_ids: Sequence[str]) -> dict[str, Movie]:
        """Movies by imdb_id; unknown IDs are absent from the result."""
        ...
