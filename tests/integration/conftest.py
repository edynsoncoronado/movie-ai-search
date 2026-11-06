"""Fixtures for the integration tests, which use the devcontainer's real services.

`pytest -m "not integration"` still collects this package, so psycopg is imported
inside the fixtures: at module level it would load the driver in unit runs (RNF2).
"""

import os
from collections.abc import Callable
from importlib import resources

import pytest

DEFAULT_TEST_DATABASE_URL = "postgresql://app:app@postgres:5432/movies_test"


@pytest.fixture(scope="session")
def test_database_url() -> str:
    """Create the test database if needed; it refuses any database not named *_test."""
    import psycopg
    from psycopg import sql
    from psycopg.conninfo import conninfo_to_dict, make_conninfo

    url = os.environ.get("TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL)
    name = str(conninfo_to_dict(url)["dbname"])
    if not name.endswith("_test"):
        pytest.exit(f"TEST_DATABASE_URL must name a *_test database, not {name!r}")

    maintenance_url = make_conninfo(url, dbname="postgres")
    with psycopg.connect(maintenance_url, autocommit=True) as connection:
        exists = connection.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (name,)
        ).fetchone()
        if exists is None:
            connection.execute(
                sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name))
            )
    return url


@pytest.fixture
def catalog_database_url(test_database_url: str) -> str:
    """The test database with `catalog.movies` present and empty.

    The DDL is applied directly, not through `ensure_schema`, so that a broken
    `ensure_schema` only fails its own tests.
    """
    import psycopg

    schema = (
        resources.files("movie_search.catalog.infrastructure")
        .joinpath("schema.sql")
        .read_text(encoding="utf-8")
    )
    with psycopg.connect(test_database_url, autocommit=True) as connection:
        connection.execute(schema)
        connection.execute("TRUNCATE catalog.movies")
    return test_database_url


@pytest.fixture
def drop_catalog_schema(catalog_database_url: str) -> Callable[[], None]:
    """Leave the database as it is before the first `ingest`: no catalog schema."""
    import psycopg

    def drop() -> None:
        with psycopg.connect(catalog_database_url, autocommit=True) as connection:
            connection.execute("DROP SCHEMA IF EXISTS catalog CASCADE")

    return drop
