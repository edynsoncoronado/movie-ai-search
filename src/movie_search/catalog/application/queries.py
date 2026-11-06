"""Read use cases that the catalog publishes to other modules (RF5, RF7)."""

from collections.abc import Iterator, Sequence

from movie_search.catalog.application.ports import MovieRepository
from movie_search.catalog.domain.models import Movie


class ListMovies:
    def __init__(self, repository: MovieRepository) -> None:
        self._repository = repository

    def execute(self) -> Iterator[Movie]:
        return self._repository.iter_all()


class GetMovies:
    def __init__(self, repository: MovieRepository) -> None:
        self._repository = repository

    def execute(self, imdb_ids: Sequence[str]) -> dict[str, Movie]:
        return self._repository.get_many(imdb_ids)
