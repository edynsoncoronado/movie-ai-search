"""A validated search query (RF7, RF8)."""

from dataclasses import dataclass

MAX_QUERY_LENGTH = 500
DEFAULT_LIMIT = 10
MAX_LIMIT = 50


class InvalidSearchQuery(ValueError):
    """The query text or the limit is out of bounds."""


@dataclass(frozen=True, slots=True)
class SearchQuery:
    """`text` is trimmed; raises `InvalidSearchQuery` when text or limit is invalid."""

    text: str
    limit: int = DEFAULT_LIMIT

    def __post_init__(self) -> None:
        text = self.text.strip()
        if not text:
            raise InvalidSearchQuery("The query is empty.")
        if len(text) > MAX_QUERY_LENGTH:
            raise InvalidSearchQuery(
                f"The query is longer than {MAX_QUERY_LENGTH} characters."
            )
        if not 1 <= self.limit <= MAX_LIMIT:
            raise InvalidSearchQuery(f"The limit must be between 1 and {MAX_LIMIT}.")
        # Frozen dataclass: the trimmed text is stored through object.__setattr__.
        object.__setattr__(self, "text", text)
