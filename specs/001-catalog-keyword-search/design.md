# 001 · Catalog ingestion and keyword search (BM25) — Design

Covers the RFs and RNFs in `requirements.md`. Layers, import rules, router factories, the composition-root rules and the general test levels are in `docs/architecture.md` and are not repeated here. Ports, types, schemas and settings are defined here; once implemented, the code is the reference.

## Architecture changes
None. This spec implements key decisions 10–12 and 15 of `docs/architecture.md`, which are already recorded. The import contracts are introduced in `pyproject.toml` by T01 (see *Import contracts*).

## Overview

```
ingest:  JSONL ─▶ JsonlMovieSource ─▶ ImportMovies ─▶ parse_line ─▶ PostgresMovieRepository   (catalog.movies)
index:   catalog.ListMovies ─▶ IndexMovies ─▶ keyword_text ─▶ QdrantKeywordIndex.rebuild  (new collection + alias swap)
search:  GET /search ─▶ SearchMovies ─▶ QdrantKeywordIndex.search ─▶ catalog.GetMovies ─▶ rank
```

## Components

### catalog

| Layer | Component | Responsibility | RF |
|---|---|---|---|
| domain | `Movie` (frozen dataclass) | `imdb_id`, `title`, `year`, `plot`, `genres`, `directors`, `writers`, `actors`, `languages`, `countries`, `runtime_min`, `imdb_votes`, `imdb_rating`, `rated`, `awards`, `poster_url`. Lists are `tuple[str, ...]`. | RF3 |
| domain | `SourceLine(line_number: int, text: str \| None)` | One physical line. `text` is `None` when the line is not valid UTF-8. | RF1, RF2 |
| domain | `SkipReason` (`StrEnum`) | `invalid_record`, `missing_imdb_id`, `invalid_response`, `not_a_movie`, `missing_title`, `missing_plot`, in RF2 order. | RF2 |
| domain | `SkippedRecord(line_number, imdb_id: str \| None, reason)` | A rejected line. | RF2 |
| domain | `parse_line(line: SourceLine) -> Movie \| SkippedRecord` | `json.loads`, the shape check, trimming, the RF2 checks in order, then normalization. | RF2, RF3 |
| domain | `parse_year`, `parse_minutes`, `parse_int`, `parse_float`, `split_list`, `parse_languages` | Pure functions behind RF3. Values that do not match → `None` / `()`. | RF3 |
| domain | `SourceUnavailable`, `CatalogUnavailable` (exceptions) | Missing or unreadable file; PostgreSQL unreachable. | RF1, RF10 |
| application | `MovieSource`, `MovieRepository` (ports) | See *Ports*. | — |
| application | `ImportReport(read, inserted, updated, skipped: Mapping[SkipReason, int])` | `read` counts non-blank lines. | RF2 |
| application | `ImportInterrupted(report: ImportReport)` (exception) | Raised when `upsert_many` raises `CatalogUnavailable`, with the counts so far, even when the first batch fails (inserted = updated = 0). | RF1 |
| application | `ImportMovies.execute(path: Path, limit: int \| None = None) -> ImportReport` | Opens the source first, skips blank lines, logs each skip, upserts in batches of 500 and stops once inserted + updated reaches `limit` (the last batch is cut so that exactly `limit` movies are stored). | RF1, RF2, RF4 |
| application | `ListMovies.execute() -> Iterator[Movie]` | Streams the whole catalog ordered by `imdb_id`, for `search`. | RF5 |
| application | `GetMovies.execute(imdb_ids: Sequence[str]) -> dict[str, Movie]` | Bulk lookup for `search`. Unknown IDs are absent from the result. | RF7 |
| application | `__init__.py` (public API) | Exports `ImportMovies`, `ListMovies`, `GetMovies`, `ImportReport`, `ImportInterrupted`, and the published types `Movie`, `SkipReason`, `SourceUnavailable` and `CatalogUnavailable` (re-exported from the domain). | — |
| infrastructure | `JsonlMovieSource` | Opens the file in binary mode (raises `SourceUnavailable` if it cannot) and decodes each line as UTF-8; an invalid line → `text=None`. | RF1, RF2 |
| infrastructure | `PostgresMovieRepository` + `schema.sql` | `ensure_schema`, upsert with inserted/updated detection, streaming read, bulk get. `psycopg.OperationalError` → `CatalogUnavailable`. | RF1, RF4, RF5, RF7, RF10 |
| entrypoints | `cli.register(subparsers, import_movies_factory, default_path)` | The `ingest` command. | RF1, RF2 |

### search

| Layer | Component | Responsibility | RF |
|---|---|---|---|
| domain | `IndexableMovie(imdb_id, title, directors, actors, genres, plot)` | The fields RF6 uses, mapped from `catalog.Movie` in `application`. | RF6 |
| domain | `KeywordDocument(imdb_id, text)` | What the keyword index receives. | RF5, RF6 |
| domain | `keyword_text(movie: IndexableMovie) -> str` | One line per part: title, title again, directors, actors, genres (each joined with `", "`), plot. Empty parts are left out. | RF6 |
| domain | `KeywordHit(imdb_id, score: float)` | What the keyword index returns. | RF7 |
| domain | `MovieSummary(imdb_id, title, year, genres, imdb_rating, poster_url, plot)` + `SearchResult(movie, score)` | The search result. Published through `search.application`. | RF7 |
| domain | `SearchQuery(text, limit)` + `MAX_QUERY_LENGTH = 500`, `DEFAULT_LIMIT = 10`, `MAX_LIMIT = 50` | Trims and validates, and raises `InvalidSearchQuery`. The HTTP schema reuses the constants. | RF7, RF8 |
| domain | `rank(results) -> list[SearchResult]` | Sorts by `(-score, imdb_id)`. The tie-break is domain code (constitution §3). | RF7 |
| domain | `SearchUnavailable` (exception) | The keyword index or the catalog cannot be reached. | RF10 |
| application | `KeywordIndex` (port) | See *Ports*. | — |
| application | `IndexReport(indexed: int)` | Index result. | RF5 |
| application | `IndexMovies.execute() -> IndexReport` | `ListMovies` → `IndexableMovie` → `KeywordDocument` → `KeywordIndex.rebuild`. | RF5, RF6 |
| application | `SearchMovies.execute(text: str, limit: int = DEFAULT_LIMIT) -> list[SearchResult]` | `SearchQuery` → `KeywordIndex.search` → `GetMovies`. Hits missing from the catalog are dropped with a warning. Then `rank`. `CatalogUnavailable` is re-raised as `SearchUnavailable`. | RF7, RF9, RF10 |
| application | `__init__.py` (public API) | Exports `IndexMovies`, `SearchMovies`, `IndexReport`, and the published types `SearchResult`, `MovieSummary`, `InvalidSearchQuery`, `SearchUnavailable` and the constants `MAX_QUERY_LENGTH`, `DEFAULT_LIMIT`, `MAX_LIMIT` (re-exported from the domain). | — |
| infrastructure | `fold_diacritics(text) -> str` (in `text_folding.py`, no fastembed import) | NFKD, then drop the combining marks. Characters with no decomposition (`ø`, `ß`) are kept. | RF6 |
| infrastructure | `QdrantKeywordIndex` | fastembed `SparseTextEmbedding("Qdrant/bm25", avg_len=BM25_AVG_LEN)`, built once and injected. Folds diacritics on **both** the documents and the queries before fastembed (fastembed only lowercases). Writes the collections and swaps the alias. Error translation (see *Errors*). | RF5, RF6, RF7, RF9, RF10, RNF1 |
| entrypoints | `http.build_router(search_movies) -> APIRouter` | `GET /search`: validation, response schema, `SearchUnavailable` → 503. | RF7–RF10 |
| entrypoints | `cli.register(subparsers, index_movies_factory)` | The `index` command. | RF5 |

### answering and shared
- `answering`: an empty package, required by the import contracts.
- `shared`: nothing in this spec.

### Composition root
- **`bootstrap.py`**:
  - `Settings`;
  - cached builders (`functools.cache`) for the Qdrant client and the BM25 model (once per process, RNF1);
  - the factories `build_import_movies()`, `build_index_movies()` and `build_search_movies()`.
  - Builders import their adapters inside the function body (deferred imports), so importing `bootstrap` loads no driver or model: `Settings` stays unit-testable, and `ingest` never imports fastembed or qdrant-client (architecture decision 15).
  - `build_import_movies()` and `build_index_movies()` call `PostgresMovieRepository.ensure_schema()`. If it fails, the builder raises `CatalogUnavailable` before any line is read. The API never runs DDL.
- **`main.py`**: at import time, calls `build_search_movies()` (this loads the BM25 model once, before the first request) and mounts the router with `search_http.build_router(...)`. Importing `movie_search.main` therefore loads the model (and downloads it on a fresh cache): no unit test imports it.
- **`cli.py`**: an `argparse` root and `logging.basicConfig(level=LOG_LEVEL)`. Each command receives a factory, so `ingest` never loads fastembed.

## Ports

```python
# catalog/application/ports.py
class MovieSource(Protocol):
    def open(self, path: Path) -> Iterator[SourceLine]: ...
        # raises SourceUnavailable before yielding if the file is missing or unreadable

class MovieRepository(Protocol):
    def upsert_many(self, movies: Sequence[Movie]) -> UpsertResult: ...   # UpsertResult(inserted: int, updated: int)
    def iter_all(self) -> Iterator[Movie]: ...                            # ordered by imdb_id
    def get_many(self, imdb_ids: Sequence[str]) -> dict[str, Movie]: ...
        # all three raise CatalogUnavailable when PostgreSQL cannot be reached

# search/application/ports.py
class KeywordIndex(Protocol):
    def rebuild(self, documents: Iterable[KeywordDocument]) -> int: ...
        # builds a new index, swaps it in atomically and returns the number of documents indexed;
        # on failure the previous index stays in place and the error propagates
    def search(self, query: str, limit: int) -> list[KeywordHit]: ...
        # [] if the index does not exist, is empty, or the query yields no tokens;
        # raises SearchUnavailable if the index cannot be reached
```

The port takes and returns plain text and `KeywordHit`s. Folding, tokenization, BM25 weights and Qdrant stay in the adapter (`docs/architecture.md` § *Modules*, rules for ports; decision 10).

## Storage

### PostgreSQL: `catalog/infrastructure/schema.sql`
Idempotent DDL, applied by `ensure_schema()` before `ingest` and `index`. There is no migration tool.

```sql
CREATE SCHEMA IF NOT EXISTS catalog;

CREATE TABLE IF NOT EXISTS catalog.movies (
    imdb_id      text PRIMARY KEY,
    title        text        NOT NULL,
    year         smallint,
    plot         text        NOT NULL,
    genres       text[]      NOT NULL DEFAULT '{}',
    directors    text[]      NOT NULL DEFAULT '{}',
    writers      text[]      NOT NULL DEFAULT '{}',
    actors       text[]      NOT NULL DEFAULT '{}',
    languages    text[]      NOT NULL DEFAULT '{}',
    countries    text[]      NOT NULL DEFAULT '{}',
    runtime_min  integer,
    imdb_votes   integer,
    imdb_rating  real,
    rated        text,
    awards       text,
    poster_url   text,
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now()
);
```

- **Upsert (RF4)**:
  - `INSERT … ON CONFLICT (imdb_id) DO UPDATE SET … , updated_at = now() RETURNING (xmax = 0) AS inserted`, via `executemany(..., returning=True)`;
  - one statement per row, so an ID repeated inside a batch is applied in file order (the last one wins) and counted as `updated`.
- **Transactions (RF1)**: one transaction per batch of 500. When the catalog fails mid-run, the committed batches remain and `ImportInterrupted` carries the counts so far.
- **No CHECK constraints** beyond `NOT NULL`: the domain guarantees the values, and a DB rejection would abort the batch instead of skipping the record.
- **Reads**:
  - `iter_all` uses a named (server-side) cursor;
  - `get_many` uses `WHERE imdb_id = ANY(%s)`;
  - if the table does not exist yet (the API before any `ingest`), `get_many` returns `{}`.
- **Connections**: one connection per call, with `connect_timeout = DATABASE_CONNECT_TIMEOUT_SECONDS`. There is no pool in 001.

### Qdrant: keyword collection behind an alias
- **Alias**: `QDRANT_KEYWORD_ALIAS` (default `movies_keyword`). `/search` only ever queries the alias.
- **Collections**: `<alias>__<UTC yyyymmddHHMMSSffffff>` (double underscore, 20 digits), one per `index` run.
  - **Config**: no dense vectors; `sparse_vectors_config = {"bm25": SparseVectorParams(modifier=Modifier.IDF)}`.
  - **Point ID**: `uuid5(NAMESPACE_URL, "https://www.imdb.com/title/{imdb_id}/")`.
  - **Payload**: `{"imdb_id": …}` only (architecture: results are completed from the catalog).
- **`rebuild`**:
  1. create the new collection;
  2. fold diacritics, embed (`SparseTextEmbedding.embed`) and upsert in batches of `INDEX_BATCH_SIZE` (`wait=True`);
  3. read the current aliases (`get_aliases`); in one `update_collection_aliases` call, delete the alias **only if it already exists** and create it pointing to the new collection (an atomic swap; on the first run there is only the create);
  4. delete every collection whose name matches `^<alias>__\d{20}$` other than the new one, which removes the previous index and any orphans. The strict pattern never touches collections of another alias (e.g. the test alias `movies_keyword_test_<random>`). A failure here is logged and does not change the result.
  - On a failure before step 3, the adapter tries to delete the new collection (a failure there is only logged) and re-raises. An empty input still creates and swaps an empty collection.
- **`search`**:
  1. fold diacritics, then `SparseTextEmbedding.query_embed`;
  2. empty indices (only stopwords or punctuation) → `[]`, with no Qdrant call;
  3. `query_points(collection_name=alias, query=SparseVector(...), using="bm25", limit=limit, with_payload=["imdb_id"])`;
  4. a 404 (alias or collection missing) → `[]`.
- **BM25 parameters**: `k = 1.2` and `b = 0.75` (fastembed defaults); `avg_len = BM25_AVG_LEN` (see *Measuring `BM25_AVG_LEN`*).
- **Ties**: they are ordered by `rank` inside the returned page. When several movies tie exactly at the cut-off, Qdrant decides which ones enter.

### Measuring `BM25_AVG_LEN`
fastembed computes `|d|` as the number of tokens **after** stopword removal and stemming. Its public `token_count()` counts tokens **before** that, so it cannot be used.

- `BM25_AVG_LEN` has a fixed default in `Settings`: a provisional `60` until it is measured.
- It is measured once, by the human, on the full catalog after the first `ingest`, with a throwaway script (not committed) that applies `keyword_text` and fastembed's own analyzer: `len(bm25._stem(SimpleTokenizer.tokenize(remove_non_alphanumeric(fold_diacritics(text)))))`, averaged over all movies. Using a private fastembed API is acceptable for a one-off measurement; production code never calls it.
- The measured value replaces the default in `Settings` and is recorded in `validation.md`. Tests never measure it.

## CLI

`uv run python -m movie_search.cli <command>`

| Command | Behavior | Exit codes |
|---|---|---|
| `ingest [PATH] [--limit N]` | `PATH` defaults to `MOVIES_DATA_PATH`; `--limit` is an argparse positive-int type. Prints the report to stdout. Each skip is a `WARNING` on stderr: `skipped line=<n> imdb_id=<id\|-> reason=<code>`. | 0 ok · 1 `SourceUnavailable` or `CatalogUnavailable` from `ensure_schema` (one-line error, no report), or `ImportInterrupted` (the partial report is printed first) · 2 usage error: bad `--limit`, or no `PATH` and no `MOVIES_DATA_PATH` |
| `index` | Prints `Indexed: N`. An empty catalog → `Indexed: 0`, exit 0. | 0 ok · 1 PostgreSQL error (including `ensure_schema`) or Qdrant error, with a one-line message (the previous index is untouched) · 2 usage error |

One rule for `ingest`: a failure after writing has started always prints the partial report; a failure before it never does.

Report format (reasons in RF2 order; reasons with a count of 0 are left out):
```
Read:      47,203
Inserted:  46,963
Updated:        0
Skipped:      240
  invalid_response    28
  not_a_movie          3
  missing_plot       209
```

## HTTP

`GET /search?q=<text>&limit=<n>`
- `q`: `Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_QUERY_LENGTH)]`. The length is counted in Unicode characters, after trimming.
- `limit`: `int`, `ge=1`, `le=MAX_LIMIT`, default `DEFAULT_LIMIT`.

Response 200:
```json
{
  "query": "blade runner",
  "results": [
    {"imdb_id": "tt0083658", "title": "Blade Runner", "year": 1982,
     "genres": ["Action", "Drama", "Sci-Fi"], "imdb_rating": 8.1,
     "poster_url": "https://…", "plot": "…", "score": 17.42}
  ]
}
```

### Errors

| Situation | Raised by | HTTP | Body | RF |
|---|---|---|---|---|
| `q` missing, empty after trimming or > 500 chars; `limit` not an int or outside 1–50 | FastAPI validation | 422 | FastAPI standard `{"detail": [...]}` | RF8 |
| `InvalidSearchQuery` (defense in depth; HTTP validation catches these cases first) | `SearchQuery` | 422 | `{"detail": "<message>"}` | RF8 |
| The query yields no tokens; the alias or collection is missing or empty; nothing matches | adapter returns `[]` | 200 | `{"query": "…", "results": []}` | RF9 |
| A hit not in the catalog | `SearchMovies` drops it and logs a `WARNING` | 200 | fewer results | RF7 |
| Qdrant unreachable or timed out (`qdrant_client` `ResponseHandlingException`, 5xx `UnexpectedResponse`) | adapter → `SearchUnavailable` | 503 | `{"detail": "Search is temporarily unavailable."}` | RF10 |
| PostgreSQL unreachable (`psycopg.OperationalError`) | repository → `CatalogUnavailable` → `SearchMovies` → `SearchUnavailable` | 503 | same | RF10 |
| Anything else | — | 500 | FastAPI default | — |

The adapter catches only `qdrant_client` exceptions and never imports `httpx`. The integration test against `http://qdrant:1` checks that connection errors arrive wrapped; if a raw `httpx` error leaks, `httpx` becomes a runtime dependency (with approval) and is caught explicitly.

## Settings

New fields in `bootstrap.Settings`:

| Variable | Default | Used by |
|---|---|---|
| `DATABASE_URL` | — (required; already in `.env.example`) | `PostgresMovieRepository` |
| `DATABASE_CONNECT_TIMEOUT_SECONDS` | `5` | `PostgresMovieRepository` (RF10) |
| `QDRANT_URL` | — (required; already in `.env.example`) | `QdrantKeywordIndex` |
| `QDRANT_TIMEOUT_SECONDS` | `5` | `QdrantKeywordIndex` (RF10) |
| `QDRANT_KEYWORD_ALIAS` | `movies_keyword` | `QdrantKeywordIndex` |
| `MOVIES_DATA_PATH` | unset (already in `.env.example`) | `ingest` default path |
| `BM25_MODEL` | `Qdrant/bm25` | `QdrantKeywordIndex` |
| `BM25_AVG_LEN` | `60` (provisional; replaced by the measured value, see *Measuring `BM25_AVG_LEN`*) | `QdrantKeywordIndex` |
| `INDEX_BATCH_SIZE` | `256` | `QdrantKeywordIndex` |
| `FASTEMBED_CACHE_DIR` | `/root/.cache/huggingface/fastembed` (the devcontainer's `hf-cache` volume; fastembed defaults to a temp dir) | `QdrantKeywordIndex` |
| `LOG_LEVEL` | `INFO` | `cli.py`, `main.py` |

**`.env.example`**: add the new variables and translate the remaining Spanish comment (`# Servicios del devcontainer…`). The `OMDB_API_KEY` and `MOVIES_DATA_PATH` comments were already rewritten during the requirements clarification.

**Test-only** (read in `tests/integration/conftest.py`, not in `Settings`):
- `TEST_DATABASE_URL`: default database `movies_test` on the same server, created by a session fixture;
- the test alias: `movies_keyword_test_<random>`, dropped together with its collections after the session.

## Dependencies (first task; need the human's approval before T01)
- **Runtime**: `fastapi`, `pydantic-settings`, `psycopg[binary]`, `qdrant-client`, `fastembed`, `uvicorn`.
- **Dev**: `pytest`, `ruff`, `import-linter`, `pre-commit`, `httpx` (needed by `TestClient`).
- `uvicorn`, `pre-commit` and `httpx` are not listed in constitution §2, which allows other dependencies with the human's approval.
- **Not added**: no CLI library (`argparse`), no migration tool and no connection pool.

## Test strategy

Test names carry the RF they cover (`test_rf3_votes_with_thousands_separator`). Unit tests never import fastembed, psycopg or qdrant-client (RNF2), never import `movie_search.main` and never call a `bootstrap` builder.

| Layer | Tests | Doubles / data | RFs |
|---|---|---|---|
| `catalog.domain` | Table-driven parsers: `"N/A"`, `""`, `"  x  "`, `"20,678"`, `"104 min"`, `"7.8"`, `"2025–"`, `"1994"`, `"c. 1999"`, garbage, `"None, English"`. `parse_line`: one case per skip reason, precedence (`Response=False` + no plot → `invalid_response`; bad `imdb_id` + `Response=False` → `missing_imdb_id`), `raw` not an object, `text=None`, `raw.imdbID` ignored, and a full sample record mapped to every field. | fixture lines in `tests/fixtures/omdb_edge_cases.jsonl` | RF2, RF3 |
| `catalog.application` | `ImportMovies`: counts per reason; blank lines neither read nor skipped; `limit` counts inserted + updated; `limit=3` stores exactly 3; a `limit` that spans two batches stores the exact total; last wins within a file; a warning per skip (`caplog`); `SourceUnavailable` → no upsert; `CatalogUnavailable` on batch 1 → `ImportInterrupted` with zero counts; on batch 2 → `ImportInterrupted` with the counts of batch 1. `ListMovies` order; `GetMovies` with unknown IDs. | `InMemoryMovieSource`, `InMemoryMovieRepository` (`fail_after_batches` flag) | RF1, RF2, RF4 |
| `catalog.entrypoints` | `ingest`: explicit and default path, no path and no env → 2; `--limit 0`, `-1`, `abc` → 2; `SourceUnavailable` → 1; `CatalogUnavailable` from the factory (`ensure_schema`) → one-line error, no report, exit 1; `ImportInterrupted` → the partial report and exit 1; report format. | `create_autospec(ImportMovies)` | RF1, RF2 |
| `search.domain` | `keyword_text`: title twice, the order, missing parts left out. `SearchQuery`: trimming, empty, 500 vs 501 chars, `limit` 0/1/50/51. `rank`: equal scores → sorted by `imdb_id`. | none | RF6, RF7, RF8 |
| `search.application` | `IndexMovies`: documents passed to `rebuild`, empty catalog → 0. `SearchMovies`: order, limit, a hit missing from the catalog is dropped with a warning, an empty index → `[]`, `SearchUnavailable` propagates, `CatalogUnavailable` → `SearchUnavailable`. | `InMemoryKeywordIndex` (term-match scoring, `unavailable` flag, keeps the last rebuild), catalog use cases over `InMemoryMovieRepository` | RF5, RF6, RF7, RF9, RF10 |
| `search.infrastructure` (unit) | `fold_diacritics`: `Amélie` → `Amelie`, `Almodóvar` → `Almodovar`, `ø` kept. | none | RF6 |
| `search.entrypoints` | `TestClient`: response shape, nullable fields, `q` trimmed, each 422 case, `results: []`, the 503 body with no internals. `index` CLI output and exit codes. | `create_autospec(SearchMovies)`, `create_autospec(IndexMovies)` | RF5, RF7–RF10 |
| `bootstrap` (unit) | `Settings` defaults and required URLs; importing `movie_search.bootstrap` leaves `fastembed`, `psycopg` and `qdrant_client` out of `sys.modules` (deferred imports). | env vars via `monkeypatch` | RNF2 |
| integration: `bootstrap` | `build_index_movies()` and `build_search_movies()` receive the same BM25 model instance (`is`). | real fastembed (cached) | RNF1 |
| integration: `catalog` | `JsonlMovieSource` on the sample, an invalid UTF-8 line (bytes written to `tmp_path`), a missing file and a directory. `PostgresMovieRepository`: `ensure_schema` twice; first upsert → inserted, second → updated; arrays and `NULL`s round-trip; `iter_all` order; `get_many` with unknown IDs; a bad URL → `CatalogUnavailable`. | real postgres (`movies_test`) | RF1, RF4, RF7, RF10 |
| integration: `search` | `QdrantKeywordIndex` over the sample: `rebuild` on a fresh Qdrant (no alias yet); `rebuild` twice → one collection behind the alias with 200 points; a collection of another alias with the same prefix (e.g. `movies_keyword_test_other__…`) survives a rebuild; a failure injected before the swap → the old alias is untouched and the partial collection is deleted; `search("Blade Runner")` → tt0083658 first; `search("Denis Villeneuve")` → tt1856101 in the top 3; `search("Coco")` → tt2380307 in the top 3; a synthetic document `Amélie` is found by `Amelie`; a stopwords-only query → `[]`; a missing alias → `[]`; `http://qdrant:1` → `SearchUnavailable`. | real qdrant + fastembed (cached) | RF5, RF6, RF7, RF9, RF10 |
| integration: end-to-end | Ingest the sample → index → `GET /search?q=Blade Runner` through `TestClient` → tt0083658 in the top 3. | full stack | RF1, RF5, RF7 |

- The DoD checks that need the full dataset (counts, the 4 anchor queries, including `"Amelie"` → tt0211915, which is not in the sample) are manual and are recorded in `validation.md`, together with the measured `BM25_AVG_LEN`.

## Import contracts (added in T01)
T01 adds the build system the `src/` layout needs and the six contracts below to `pyproject.toml`, which is their only source from then on (architecture decision 14).

```toml
[build-system]
requires = ["uv_build"]            # pin the version range that `uv init --package` generates
build-backend = "uv_build"

[tool.uv.build-backend]
module-name = "movie_search"       # the project is "movie-ai-search"; without this uv looks for movie_ai_search
```

```toml
[tool.importlinter]
root_package = "movie_search"
include_external_packages = true

# Modules form an acyclic graph; main and cli are independent composition roots.
[[tool.importlinter.contracts]]
name = "Capabilities dependency graph"
type = "layers"
containers = ["movie_search"]
layers = ["main | cli", "bootstrap", "answering", "search", "catalog", "shared"]

# Clean Architecture layers inside each capability; entrypoints is optional.
[[tool.importlinter.contracts]]
name = "Clean Architecture layers inside each capability"
type = "layers"
containers = ["movie_search.catalog", "movie_search.search", "movie_search.answering"]
layers = ["(entrypoints) | infrastructure", "application", "domain"]

# Inner layers stay framework-free.
[[tool.importlinter.contracts]]
name = "Domain, application and shared are framework-free"
type = "forbidden"
source_modules = [
  "movie_search.catalog.domain", "movie_search.catalog.application",
  "movie_search.search.domain", "movie_search.search.application",
  "movie_search.answering.domain", "movie_search.answering.application",
  "movie_search.shared",
]
forbidden_modules = ["fastapi", "pydantic", "pydantic_settings", "psycopg", "qdrant_client", "fastembed", "openai", "anthropic", "httpx"]

# Modules use each other only through `application`.
[[tool.importlinter.contracts]]
name = "search uses catalog only through catalog.application"
type = "forbidden"
allow_indirect_imports = true
source_modules = ["movie_search.search"]
forbidden_modules = ["movie_search.catalog.domain", "movie_search.catalog.infrastructure", "movie_search.catalog.entrypoints"]

[[tool.importlinter.contracts]]
name = "answering uses search and catalog only through their application"
type = "forbidden"
allow_indirect_imports = true
source_modules = ["movie_search.answering"]
forbidden_modules = [
  "movie_search.search.domain", "movie_search.search.infrastructure", "movie_search.search.entrypoints",
  "movie_search.catalog.domain", "movie_search.catalog.infrastructure", "movie_search.catalog.entrypoints",
]

# A domain imports only the stdlib and shared.
[[tool.importlinter.contracts]]
name = "Domains import no other capability"
type = "forbidden"
source_modules = ["movie_search.search.domain", "movie_search.answering.domain"]
forbidden_modules = ["movie_search.catalog", "movie_search.search.application", "movie_search.search.infrastructure", "movie_search.search.entrypoints"]
```

The contracts were tested with import-linter 2.5.2 on an empty skeleton of this layout: all legitimate imports pass (including a published type re-exported from `search.application`) and 13 forbidden imports are all caught.

## Out of this design
- Dense vectors and RRF (002); filters and payload indexes (003).
- Connection pooling and latency work (004).
