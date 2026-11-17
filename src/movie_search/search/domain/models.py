from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class IndexableMovie:
    """The catalog fields that make up a movie's keyword text (RF6)."""

    imdb_id: str
    title: str
    directors: tuple[str, ...] = ()
    actors: tuple[str, ...] = ()
    genres: tuple[str, ...] = ()
    plot: str


@dataclass(frozen=True, slots=True)
class KeywordDocument:
    """What the keyword index receives for one movie."""

    imdb_id: str
    text: str


@dataclass(frozen=True, slots=True)
class KeywordHit:
    """What the keyword index returns: a movie and its raw BM25 score."""

    imdb_id: str
    score: float


@dataclass(frozen=True, slots=True, kw_only=True)
class MovieSummary:
    imdb_id: str
    title: str
    year: int | None = None
    genres: tuple[str, ...] = ()
    imdb_rating: float | None = None
    poster_url: str | None = None
    plot: str


@dataclass(frozen=True, slots=True)
class SearchResult:
    movie: MovieSummary
    score: float
