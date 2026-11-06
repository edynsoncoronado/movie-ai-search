"""`JsonlMovieSource` over real files (RF1, RF2)."""

import json
from pathlib import Path

import pytest

from movie_search.catalog.domain.errors import SourceUnavailable
from movie_search.catalog.infrastructure.jsonl_source import JsonlMovieSource

pytestmark = pytest.mark.integration

SAMPLE_PATH = Path(__file__).parents[3] / "data" / "sample" / "omdb_sample.jsonl"


def test_rf1_source_reads_sample_200_lines() -> None:
    lines = list(JsonlMovieSource().open(SAMPLE_PATH))

    assert [line.line_number for line in lines] == list(range(1, 201))
    assert json.loads(lines[0].text)["imdb_id"] == "tt0032145"


def test_rf2_source_invalid_utf8_line_has_text_none(tmp_path: Path) -> None:
    path = tmp_path / "invalid_utf8.jsonl"
    path.write_bytes(
        b'{"position": "first"}\n\xff\xfe not utf-8\n{"position": "last"}\n'
    )

    lines = list(JsonlMovieSource().open(path))

    assert [line.line_number for line in lines] == [1, 2, 3]
    assert json.loads(lines[0].text) == {"position": "first"}
    assert lines[1].text is None
    assert json.loads(lines[2].text) == {"position": "last"}


def test_rf1_source_missing_file_raises_source_unavailable(tmp_path: Path) -> None:
    with pytest.raises(SourceUnavailable):
        list(JsonlMovieSource().open(tmp_path / "missing.jsonl"))


def test_rf1_source_directory_raises_source_unavailable(tmp_path: Path) -> None:
    with pytest.raises(SourceUnavailable):
        list(JsonlMovieSource().open(tmp_path))
