"""Settings and the builders that wire adapters into use cases.

Builders import their adapters inside the function body, so importing this module
loads no driver or model and each entry point builds only what it needs.
"""

from functools import cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from movie_search.catalog.application import ImportMovies


class Settings(BaseSettings):
    # hide_input_in_errors: a validation error would otherwise print DATABASE_URL.
    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore",
        hide_input_in_errors=True,
    )

    database_url: str
    database_connect_timeout_seconds: int = 5
    qdrant_url: str
    qdrant_timeout_seconds: int = 5
    qdrant_keyword_alias: str = "movies_keyword"
    movies_data_path: Path | None = None
    bm25_model: str = "Qdrant/bm25"
    bm25_avg_len: float = 60  # provisional until measured on the full catalog
    index_batch_size: int = 256
    fastembed_cache_dir: str = "/root/.cache/huggingface/fastembed"
    log_level: str = "INFO"


@cache
def get_settings() -> Settings:
    return Settings()


def build_import_movies() -> ImportMovies:
    """Raises CatalogUnavailable if the catalog schema cannot be applied."""
    from movie_search.catalog.infrastructure.jsonl_source import JsonlMovieSource
    from movie_search.catalog.infrastructure.postgres_repository import (
        PostgresMovieRepository,
    )

    settings = get_settings()
    repository = PostgresMovieRepository(
        settings.database_url,
        connect_timeout_seconds=settings.database_connect_timeout_seconds,
    )
    repository.ensure_schema()
    return ImportMovies(JsonlMovieSource(), repository)
