"""`Settings` and the import-time behavior of `bootstrap` (RF1, RNF2)."""

import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from movie_search.bootstrap import Settings

DATABASE_URL = "postgresql://user:s3cret@db:5432/movies"
QDRANT_URL = "http://vector-store:6333"


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """The devcontainer may export these variables; `_env_file=None` skips `.env`."""
    for name in Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)


def test_settings_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
    monkeypatch.setenv("QDRANT_URL", QDRANT_URL)

    settings = Settings(_env_file=None)

    assert settings.database_url == DATABASE_URL
    assert settings.database_connect_timeout_seconds == 5
    assert settings.qdrant_url == QDRANT_URL
    assert settings.qdrant_timeout_seconds == 5
    assert settings.qdrant_keyword_alias == "movies_keyword"
    assert settings.movies_data_path is None
    assert settings.bm25_model == "Qdrant/bm25"
    # Provisional default, replaced by the measured value in T11: not pinned here.
    assert settings.bm25_avg_len > 0
    assert settings.index_batch_size == 256
    assert settings.fastembed_cache_dir == "/root/.cache/huggingface/fastembed"
    assert settings.log_level == "INFO"


@pytest.mark.parametrize(
    ("present", "missing"),
    [("DATABASE_URL", "qdrant_url"), ("QDRANT_URL", "database_url")],
)
def test_settings_requires_database_and_qdrant_urls(
    present: str, missing: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(present, "scheme://host")

    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None)

    assert [item["loc"] for item in error.value.errors()] == [(missing,)]


def test_settings_validation_error_hides_the_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)

    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None)

    assert "s3cret" not in str(error.value)


def test_rf1_settings_reads_movies_data_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
    monkeypatch.setenv("QDRANT_URL", QDRANT_URL)
    monkeypatch.setenv("MOVIES_DATA_PATH", "data/omdb_raw.jsonl")

    assert Settings(_env_file=None).movies_data_path == Path("data/omdb_raw.jsonl")


def test_rf1_settings_empty_movies_data_path_is_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
    monkeypatch.setenv("QDRANT_URL", QDRANT_URL)
    monkeypatch.setenv("MOVIES_DATA_PATH", "")

    assert Settings(_env_file=None).movies_data_path is None


def test_rnf2_importing_bootstrap_loads_no_driver() -> None:
    # A new interpreter: sys.modules here depends on what other tests imported.
    code = (
        "import sys, movie_search.bootstrap;"
        "print(*(name for name in ('fastembed', 'psycopg', 'qdrant_client')"
        " if name in sys.modules))"
    )

    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )

    assert result.stdout.strip() == ""
