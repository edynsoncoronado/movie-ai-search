"""`MovieRepository` adapter over PostgreSQL (RF1, RF4, RF5, RF7, RF10)."""

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import fields
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from movie_search.catalog.application.ports import UpsertResult
from movie_search.catalog.domain.errors import CatalogUnavailable
from movie_search.catalog.domain.models import Movie

_SCHEMA_PATH = Path(__file__).with_name("schema.sql")

_LIST_COLUMNS = ("genres", "directors", "writers", "actors", "languages", "countries")
_COLUMNS = tuple(field.name for field in fields(Movie))
_SELECT_COLUMNS = ", ".join(_COLUMNS)
_UPDATED_COLUMNS = tuple(column for column in _COLUMNS if column != "imdb_id")

_UPSERT = f"""
    INSERT INTO catalog.movies ({_SELECT_COLUMNS})
    VALUES ({", ".join(f"%({column})s" for column in _COLUMNS)})
    ON CONFLICT (imdb_id) DO UPDATE SET
        {", ".join(f"{column} = EXCLUDED.{column}" for column in _UPDATED_COLUMNS)},
        updated_at = now()
    RETURNING (xmax = 0) AS inserted
"""
_SELECT_ALL = f"SELECT {_SELECT_COLUMNS} FROM catalog.movies ORDER BY imdb_id"
_SELECT_MANY = f"SELECT {_SELECT_COLUMNS} FROM catalog.movies WHERE imdb_id = ANY(%s)"


class PostgresMovieRepository:
    """Opens one connection per call; each `upsert_many` is one transaction."""

    def __init__(self, database_url: str, *, connect_timeout_seconds: int) -> None:
        self._database_url = database_url
        self._connect_timeout_seconds = connect_timeout_seconds

    def ensure_schema(self) -> None:
        with _catalog_errors(), self._connect() as connection:
            connection.execute(_SCHEMA_PATH.read_text(encoding="utf-8"))

    def upsert_many(self, movies: Sequence[Movie]) -> UpsertResult:
        with (
            _catalog_errors(),
            self._connect() as connection,
            connection.cursor() as cursor,
        ):
            cursor.executemany(
                _UPSERT, [_to_row(movie) for movie in movies], returning=True
            )
            flags = _inserted_flags(cursor)
        inserted = sum(flags)
        return UpsertResult(inserted=inserted, updated=len(flags) - inserted)

    def iter_all(self) -> Iterator[Movie]:
        with (
            _catalog_errors(),
            self._connect() as connection,
            connection.cursor(name="catalog_iter_all", row_factory=dict_row) as cursor,
        ):
            cursor.execute(_SELECT_ALL)
            for row in cursor:
                yield _to_movie(row)

    def get_many(self, imdb_ids: Sequence[str]) -> dict[str, Movie]:
        try:
            with (
                _catalog_errors(),
                self._connect() as connection,
                connection.cursor(row_factory=dict_row) as cursor,
            ):
                cursor.execute(_SELECT_MANY, (list(imdb_ids),))
                return {row["imdb_id"]: _to_movie(row) for row in cursor}
        except psycopg.errors.UndefinedTable:
            # The API can run before the first `ingest` has created the table.
            return {}

    def _connect(self) -> psycopg.Connection[Any]:
        return psycopg.connect(
            self._database_url, connect_timeout=self._connect_timeout_seconds
        )


@contextmanager
def _catalog_errors() -> Iterator[None]:
    try:
        yield
    except psycopg.OperationalError as error:
        raise CatalogUnavailable("the catalog database is unavailable") from error


def _inserted_flags(cursor: psycopg.Cursor[Any]) -> list[bool]:
    """One flag per upserted row: `executemany` leaves one result set for each."""
    flags = []
    while True:
        flags.append(cursor.fetchone()[0])
        if not cursor.nextset():
            return flags


def _to_row(movie: Movie) -> dict[str, Any]:
    row = {column: getattr(movie, column) for column in _COLUMNS}
    return row | {column: list(row[column]) for column in _LIST_COLUMNS}


def _to_movie(row: dict[str, Any]) -> Movie:
    return Movie(**row | {column: tuple(row[column]) for column in _LIST_COLUMNS})
