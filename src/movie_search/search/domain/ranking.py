"""Result ordering (RF7)."""

from collections.abc import Iterable

from movie_search.search.domain.models import SearchResult


def rank(results: Iterable[SearchResult]) -> list[SearchResult]:
    """Sort by descending score; equal scores by ascending `imdb_id`."""
    return sorted(results, key=lambda result: (-result.score, result.movie.imdb_id))
