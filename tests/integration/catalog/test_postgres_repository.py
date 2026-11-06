"""`PostgresMovieRepository` against the real postgres, database `movies_test`.

The adapter is imported inside `_repository`: `pytest -m "not integration"` still
collects this module, and a module-level import would load psycopg in unit runs (RNF2).
"""

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import pytest

from movie_search.catalog.application.ports import UpsertResult
from movie_search.catalog.domain.errors import CatalogUnavailable
from movie_search.catalog.domain.models import Movie

if TYPE_CHECKING:
    from movie_search.catalog.infrastructure.postgres_repository import (
        PostgresMovieRepository,
    )

pytestmark = pytest.mark.integration

UNREACHABLE_DATABASE_URL = "postgresql://app:app@postgres:1/movies_test"


def _repository(url: str) -> "PostgresMovieRepository":
    from movie_search.catalog.infrastructure.postgres_repository import (
        PostgresMovieRepository,
    )

    return PostgresMovieRepository(url, connect_timeout_seconds=1)


def _movie(imdb_id: str, title: str = "A title") -> Movie:
    return Movie(imdb_id=imdb_id, title=title, plot="A plot.")


@pytest.fixture
def repository(catalog_database_url: str) -> "PostgresMovieRepository":
    return _repository(catalog_database_url)


def test_ensure_schema_is_idempotent(
    catalog_database_url: str, drop_catalog_schema: Callable[[], None]
) -> None:
    drop_catalog_schema()
    repository = _repository(catalog_database_url)
    movie = _movie("tt0000001")

    repository.ensure_schema()
    repository.upsert_many([movie])
    repository.ensure_schema()

    assert repository.get_many(["tt0000001"]) == {"tt0000001": movie}


def test_rf4_first_upsert_inserted_second_updated(
    repository: "PostgresMovieRepository",
) -> None:
    changed = _movie("tt0000001", title="Changed title")

    first = repository.upsert_many([_movie("tt0000001", title="Original title")])
    second = repository.upsert_many([changed, _movie("tt0000002")])

    assert first == UpsertResult(inserted=1, updated=0)
    assert second == UpsertResult(inserted=1, updated=1)
    assert repository.get_many(["tt0000001"]) == {"tt0000001": changed}


def test_rf4_repeated_id_in_batch_last_wins(
    repository: "PostgresMovieRepository",
) -> None:
    last = _movie("tt0000001", title="Last")
    other = _movie("tt0000002")

    result = repository.upsert_many([_movie("tt0000001", title="First"), other, last])

    assert result == UpsertResult(inserted=2, updated=1)
    assert list(repository.iter_all()) == [last, other]


def test_rf3_arrays_and_nulls_round_trip(
    repository: "PostgresMovieRepository",
) -> None:
    full = Movie(
        imdb_id="tt0211915",
        title="Amélie",
        year=2001,
        plot="A shy waitress decides to change the lives of those around her.",
        genres=("Comedy", "Romance"),
        directors=("Jean-Pierre Jeunet",),
        writers=("Guillaume Laurant", "Jean-Pierre Jeunet"),
        actors=("Audrey Tautou", "Conan O'Brien", 'Dwayne "The Rock" Johnson'),
        languages=("French", "Russian"),
        countries=("France", "Germany"),
        runtime_min=122,
        imdb_votes=812345,
        imdb_rating=8.3,
        rated="R",
        awards="Nominated for 5 Oscars.",
        poster_url="https://example.com/amelie.jpg",
    )
    only_required = Movie(imdb_id="tt0000002", title="Sparse", plot="Required only.")

    repository.upsert_many([full, only_required])

    assert repository.get_many(["tt0211915", "tt0000002"]) == {
        "tt0211915": full,
        "tt0000002": only_required,
    }
    assert list(repository.iter_all()) == [only_required, full]


def test_iter_all_ordered_by_imdb_id(repository: "PostgresMovieRepository") -> None:
    first, second, third = (_movie(f"tt000000{n}") for n in (1, 2, 3))
    repository.upsert_many([third, first])
    repository.upsert_many([second])

    assert list(repository.iter_all()) == [first, second, third]


def test_rf7_get_many_omits_unknown_ids(
    repository: "PostgresMovieRepository",
) -> None:
    known = _movie("tt0000001")
    repository.upsert_many([known, _movie("tt0000002")])

    assert repository.get_many(["tt0000001", "tt9999999"]) == {"tt0000001": known}


def test_rf7_get_many_missing_table_returns_empty(
    repository: "PostgresMovieRepository",
    drop_catalog_schema: Callable[[], None],
) -> None:
    drop_catalog_schema()

    assert repository.get_many(["tt0000001"]) == {}


@pytest.mark.parametrize(
    "call",
    [
        pytest.param(lambda repo: repo.ensure_schema(), id="ensure_schema"),
        pytest.param(
            lambda repo: repo.upsert_many([_movie("tt0000001")]), id="upsert_many"
        ),
        pytest.param(lambda repo: list(repo.iter_all()), id="iter_all"),
        pytest.param(lambda repo: repo.get_many(["tt0000001"]), id="get_many"),
    ],
)
def test_rf10_unreachable_database_raises_catalog_unavailable(
    call: Callable[["PostgresMovieRepository"], Any],
) -> None:
    repository = _repository(UNREACHABLE_DATABASE_URL)

    with pytest.raises(CatalogUnavailable):
        call(repository)
