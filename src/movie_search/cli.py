"""Composition root of the CLI: `python -m movie_search.cli <command>`."""

import argparse
import logging
import sys
from collections.abc import Sequence

from movie_search.bootstrap import build_import_movies, get_settings
from movie_search.catalog.entrypoints import cli as catalog_cli


def main(argv: Sequence[str] | None = None) -> int:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(prog="movie_search.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)
    catalog_cli.register(subparsers, build_import_movies, settings.movies_data_path)

    args = parser.parse_args(argv)
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())
