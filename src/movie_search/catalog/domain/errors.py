class SourceUnavailable(Exception):
    """The movie source file is missing or cannot be read."""


class CatalogUnavailable(Exception):
    """The catalog storage (PostgreSQL) cannot be reached."""
