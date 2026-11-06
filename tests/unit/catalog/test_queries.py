"""`ListMovies` (for RF5) and `GetMovies` (for RF7) over the in-memory repository."""

from movie_search.catalog.application import GetMovies, ListMovies, Movie
from tests.fakes.catalog import InMemoryMovieRepository


def _movie(imdb_id: str) -> Movie:
    return Movie(imdb_id=imdb_id, title=f"Title of {imdb_id}", plot="A plot.")


def test_list_movies_ordered_by_imdb_id() -> None:
    repository = InMemoryMovieRepository(
        [_movie("tt0000003"), _movie("tt0000001"), _movie("tt0000002")]
    )

    movies = ListMovies(repository).execute()

    assert [movie.imdb_id for movie in movies] == [
        "tt0000001",
        "tt0000002",
        "tt0000003",
    ]


def test_get_movies_omits_unknown_ids() -> None:
    known = _movie("tt0000001")
    repository = InMemoryMovieRepository([known, _movie("tt0000002")])

    movies = GetMovies(repository).execute(["tt0000001", "tt9999999"])

    assert movies == {"tt0000001": known}
