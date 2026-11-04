"""Pure parsing and validation of OMDb records (RF2, RF3)."""

import json
import re
from collections.abc import Mapping

from movie_search.catalog.domain.models import (
    Movie,
    SkippedRecord,
    SkipReason,
    SourceLine,
)

_NOT_AVAILABLE = "N/A"
_NO_LANGUAGE = "None"

# re.ASCII: only 0-9 count as digits, so int() never sees other Unicode digits.
_IMDB_ID = re.compile(r"tt\d{7,}", re.ASCII)
_YEAR_PREFIX = re.compile(r"\d{4}", re.ASCII)
_MINUTES = re.compile(r"(\d+) min", re.ASCII)
_INTEGER = re.compile(r"\d{1,3}(?:,\d{3})+|\d+", re.ASCII)
_DECIMAL = re.compile(r"\d+(?:\.\d+)?", re.ASCII)


def _clean(value: object) -> str | None:
    """Trim a value; non-strings, empty strings and "N/A" are missing (None)."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or text == _NOT_AVAILABLE:
        return None
    return text


def parse_year(value: str | None) -> int | None:
    text = _clean(value)
    if text is None:
        return None
    match = _YEAR_PREFIX.match(text)
    return int(match.group()) if match else None


def parse_minutes(value: str | None) -> int | None:
    text = _clean(value)
    if text is None:
        return None
    match = _MINUTES.fullmatch(text)
    return int(match.group(1)) if match else None


def parse_int(value: str | None) -> int | None:
    text = _clean(value)
    if text is None or not _INTEGER.fullmatch(text):
        return None
    return int(text.replace(",", ""))


def parse_float(value: str | None) -> float | None:
    text = _clean(value)
    if text is None or not _DECIMAL.fullmatch(text):
        return None
    return float(text)


def split_list(value: str | None) -> tuple[str, ...]:
    text = _clean(value)
    if text is None:
        return ()
    parts = (part.strip() for part in text.split(","))
    return tuple(part for part in parts if part)


def parse_languages(value: str | None) -> tuple[str, ...]:
    return tuple(lang for lang in split_list(value) if lang != _NO_LANGUAGE)


def _decode(
    text: str | None,
) -> tuple[Mapping[str, object], Mapping[str, object]] | None:
    """The record and its `raw` object, or None if the line is not that shape."""
    if text is None:
        return None
    try:
        record = json.loads(text)
    except ValueError:
        return None
    if not isinstance(record, dict):
        return None
    raw = record.get("raw")
    if not isinstance(raw, dict):
        return None
    return record, raw


def _to_movie(imdb_id: str, title: str, plot: str, raw: Mapping[str, object]) -> Movie:
    def text(key: str) -> str | None:
        return _clean(raw.get(key))

    return Movie(
        imdb_id=imdb_id,
        title=title,
        year=parse_year(text("Year")),
        plot=plot,
        genres=split_list(text("Genre")),
        directors=split_list(text("Director")),
        writers=split_list(text("Writer")),
        actors=split_list(text("Actors")),
        languages=parse_languages(text("Language")),
        countries=split_list(text("Country")),
        runtime_min=parse_minutes(text("Runtime")),
        imdb_votes=parse_int(text("imdbVotes")),
        imdb_rating=parse_float(text("imdbRating")),
        rated=text("Rated"),
        awards=text("Awards"),
        poster_url=text("Poster"),
    )


def parse_line(line: SourceLine) -> Movie | SkippedRecord:
    """A movie, or the first RF2 skip reason that applies (checked in RF2 order)."""
    decoded = _decode(line.text)
    if decoded is None:
        return SkippedRecord(line.line_number, None, SkipReason.INVALID_RECORD)
    record, raw = decoded

    # The identity is the top-level imdb_id; raw.imdbID is ignored (RF2).
    imdb_id = _clean(record.get("imdb_id"))
    if imdb_id is None or not _IMDB_ID.fullmatch(imdb_id):
        return SkippedRecord(line.line_number, None, SkipReason.MISSING_IMDB_ID)

    def skip(reason: SkipReason) -> SkippedRecord:
        return SkippedRecord(line.line_number, imdb_id, reason)

    if _clean(raw.get("Response")) == "False":
        return skip(SkipReason.INVALID_RESPONSE)
    if _clean(raw.get("Type")) != "movie":
        return skip(SkipReason.NOT_A_MOVIE)
    title = _clean(raw.get("Title"))
    if title is None:
        return skip(SkipReason.MISSING_TITLE)
    plot = _clean(raw.get("Plot"))
    if plot is None:
        return skip(SkipReason.MISSING_PLOT)
    return _to_movie(imdb_id, title, plot, raw)
