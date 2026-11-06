"""`MovieSource` adapter that reads an OMDb JSONL file (RF1, RF2)."""

from collections.abc import Iterator
from pathlib import Path

from movie_search.catalog.domain.errors import SourceUnavailable
from movie_search.catalog.domain.models import SourceLine


class JsonlMovieSource:
    def open(self, path: Path) -> Iterator[SourceLine]:
        try:
            file = path.open("rb")
        except OSError as error:
            raise SourceUnavailable(f"cannot read {path}: {error}") from error
        with file:
            for number, raw in enumerate(file, start=1):
                yield SourceLine(line_number=number, text=_decode(raw))


def _decode(raw: bytes) -> str | None:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None
