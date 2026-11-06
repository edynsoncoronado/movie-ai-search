"""In-memory fakes of the catalog ports."""

from collections.abc import Iterable, Iterator, Sequence
from pathlib import Path

from movie_search.catalog.application.ports import UpsertResult
from movie_search.catalog.domain.errors import CatalogUnavailable, SourceUnavailable
from movie_search.catalog.domain.models import Movie, SourceLine


class InMemoryMovieSource:
    """Serves `texts` as numbered lines (from 1); `None` is a line that is not UTF-8."""

    def __init__(
        self, texts: Iterable[str | None] = (), *, unavailable: bool = False
    ) -> None:
        self._texts = list(texts)
        self._unavailable = unavailable

    def open(self, path: Path) -> Iterator[SourceLine]:
        if self._unavailable:
            raise SourceUnavailable(f"cannot read {path}")
        for number, text in enumerate(self._texts, start=1):
            yield SourceLine(line_number=number, text=text)


class InMemoryMovieRepository:
    """Stores movies by imdb_id, applying each batch row by row, in order.

    With `fail_after_batches=N`, the first N calls to `upsert_many` succeed and the
    next ones raise `CatalogUnavailable` without storing anything. `batches` holds the
    batches that were stored.
    """

    def __init__(
        self, movies: Iterable[Movie] = (), *, fail_after_batches: int | None = None
    ) -> None:
        self._movies = {movie.imdb_id: movie for movie in movies}
        self._fail_after_batches = fail_after_batches
        self.batches: list[tuple[Movie, ...]] = []

    def upsert_many(self, movies: Sequence[Movie]) -> UpsertResult:
        limit = self._fail_after_batches
        if limit is not None and len(self.batches) >= limit:
            raise CatalogUnavailable("catalog is down")
        self.batches.append(tuple(movies))
        inserted = updated = 0
        for movie in movies:
            if movie.imdb_id in self._movies:
                updated += 1
            else:
                inserted += 1
            self._movies[movie.imdb_id] = movie
        return UpsertResult(inserted=inserted, updated=updated)

    def iter_all(self) -> Iterator[Movie]:
        return iter(sorted(self._movies.values(), key=lambda movie: movie.imdb_id))

    def get_many(self, imdb_ids: Sequence[str]) -> dict[str, Movie]:
        return {
            imdb_id: self._movies[imdb_id]
            for imdb_id in imdb_ids
            if imdb_id in self._movies
        }
