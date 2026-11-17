"""The text a movie is indexed by for keyword search (RF6)."""

from movie_search.search.domain.models import IndexableMovie

_LIST_SEPARATOR = ", "


def keyword_text(movie: IndexableMovie) -> str:
    """One line per part: title, title again, directors, actors, genres, plot.

    The title is written twice as a title boost. List parts are joined with ", ";
    empty parts are left out.
    """
    parts = [
        movie.title,
        movie.title,
        _LIST_SEPARATOR.join(movie.directors),
        _LIST_SEPARATOR.join(movie.actors),
        _LIST_SEPARATOR.join(movie.genres),
        movie.plot,
    ]
    return "\n".join(part for part in parts if part)
