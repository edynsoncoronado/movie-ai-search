from dataclasses import dataclass
from enum import StrEnum


@dataclass(frozen=True, slots=True, kw_only=True)
class Movie:
    imdb_id: str
    title: str
    year: int | None = None
    plot: str
    genres: tuple[str, ...] = ()
    directors: tuple[str, ...] = ()
    writers: tuple[str, ...] = ()
    actors: tuple[str, ...] = ()
    languages: tuple[str, ...] = ()
    countries: tuple[str, ...] = ()
    runtime_min: int | None = None
    imdb_votes: int | None = None
    imdb_rating: float | None = None
    rated: str | None = None
    awards: str | None = None
    poster_url: str | None = None


@dataclass(frozen=True, slots=True)
class SourceLine:
    """One physical line of the source file; `text` is None when it is not UTF-8."""

    line_number: int
    text: str | None


class SkipReason(StrEnum):
    """Why a record was skipped, in RF2 order (the first matching reason wins)."""

    INVALID_RECORD = "invalid_record"
    MISSING_IMDB_ID = "missing_imdb_id"
    INVALID_RESPONSE = "invalid_response"
    NOT_A_MOVIE = "not_a_movie"
    MISSING_TITLE = "missing_title"
    MISSING_PLOT = "missing_plot"


@dataclass(frozen=True, slots=True)
class SkippedRecord:
    line_number: int
    imdb_id: str | None
    reason: SkipReason
