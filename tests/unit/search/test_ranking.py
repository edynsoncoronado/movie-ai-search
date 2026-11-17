"""RF7: results ordered by descending score, ties by ascending `imdb_id`."""

from movie_search.search.domain.models import MovieSummary, SearchResult
from movie_search.search.domain.ranking import rank


def _result(imdb_id: str, score: float) -> SearchResult:
    return SearchResult(
        movie=MovieSummary(
            imdb_id=imdb_id, title=f"Title of {imdb_id}", plot="A plot."
        ),
        score=score,
    )


def _ids(results: list[SearchResult]) -> list[str]:
    return [result.movie.imdb_id for result in results]


def test_rf7_rank_by_score_desc() -> None:
    results = [
        _result("tt0000001", 3.5),
        _result("tt0000002", 17.42),
        _result("tt0000003", 0.1),
        _result("tt0000004", 9.0),
    ]

    assert _ids(rank(results)) == ["tt0000002", "tt0000004", "tt0000001", "tt0000003"]


def test_rf7_equal_scores_sorted_by_imdb_id() -> None:
    results = [
        _result("tt0000009", 5.0),
        _result("tt0000001", 2.0),
        _result("tt0000007", 5.0),
        _result("tt0000003", 8.0),
        _result("tt0000005", 5.0),
    ]

    assert _ids(rank(results)) == [
        "tt0000003",
        "tt0000005",
        "tt0000007",
        "tt0000009",
        "tt0000001",
    ]
