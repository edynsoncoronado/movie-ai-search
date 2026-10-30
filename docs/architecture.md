# Architecture

movie-ai-search follows **Clean Architecture** inside a **screaming architecture**: the top-level packages name what the system does (catalog, search, query understanding, answering), and each one is split internally into layers with dependencies pointing inward.

## Package layout

```
src/movie_search/
  catalog/               # movies and their ingestion
    domain/
    application/
    infrastructure/
  search/                # hybrid search over the catalog
    domain/
    application/
    infrastructure/
    entrypoints/
  query_understanding/   # natural language -> structured filters
    domain/
    application/
    infrastructure/
  answering/             # RAG answers with citations
    domain/
    application/
    infrastructure/
    entrypoints/
  shared/                # minimal shared kernel
  main.py                # composition root (FastAPI app)
tests/
  unit/<module>/
  integration/<module>/
```

A module only has the layers it needs (for example, `catalog` has no `entrypoints/` until a spec asks for one). A new capability (for example, an `evaluation` module for nDCG@k / recall@k) is added as a new top-level module, never as a technical folder such as `utils/`, `services/` or `models/`.

## Modules

| Module | Responsibility | Main concepts | Ports (defined in `application/`) |
|---|---|---|---|
| `catalog` | Owns the movie data and its ingestion from OMDb JSONL. | `Movie`, `ImportMovies` | `MovieRepository` (postgres), `MovieSource` (JSONL) |
| `query_understanding` | Turns a natural-language query into structured filters (year, genre, rating, exclusions...). | `SearchFilters`, `ExtractFilters` | `LLMClient` |
| `search` | Indexes movies and runs hybrid search: vector + keyword, fused with RRF, then filtered. | `SearchQuery`, `SearchResult`, `rrf_fuse`, `SearchMovies`, `IndexMovies` | `VectorIndex` (qdrant), `KeywordIndex` (postgres), `Embedder` |
| `answering` | Builds a grounded answer from search results, with citations to the movies used. | `Answer`, `Citation`, `AnswerQuestion` | `LLMClient` |
| `shared` | Value objects that several modules need (e.g. `MovieId`, `Year`). | — | — |

The ports' names are guidance. The spec for each feature sets their final shape.

### Dependencies between modules

```
main ──▶ answering ──▶ search ──▶ query_understanding
                          │
                          └────▶ catalog
                 (all may use shared)
```

- The graph is acyclic. Lower modules never import higher ones.
- `query_understanding` and `catalog` are independent of each other.
- A module imports another only through its `application` public API (the names exported from `movie_search/<module>/application/__init__.py`).
- `shared` imports no capability. Keep it small: if something has behavior that belongs to one capability, it lives in that capability.

## Layers inside a module

```
entrypoints ─┐
             ├──▶ application ──▶ domain
infrastructure ┘
```

| Layer | Contains | May import | Must not import |
|---|---|---|---|
| `domain` | Entities, value objects, pure domain functions (e.g. RRF fusion, filter rules). | stdlib, `shared` | Any framework or I/O library; `application`, `infrastructure`, `entrypoints` |
| `application` | Use cases, port definitions (`typing.Protocol`), DTOs at the module boundary. | `domain`, `shared`, other modules' `application` | `infrastructure`, `entrypoints`, frameworks |
| `infrastructure` | Adapters that implement ports: postgres, qdrant, LLM/embedding clients, JSONL readers. | `application`, `domain`, external libraries | `entrypoints` |
| `entrypoints` | FastAPI routers, CLI commands. Translate input/output and call use cases. | `application`, web framework | `infrastructure` (receives use cases already wired) |

Frameworks forbidden in `domain`: `fastapi`, `pydantic_settings`, `sqlalchemy`, `psycopg`, `qdrant_client`, `openai`, `anthropic`, `httpx`. Application code uses only the ports.

## Composition root

`movie_search/main.py` is the only place that:
- reads settings (from `.env`),
- builds the concrete adapters,
- injects them into the use cases,
- mounts the routers on the FastAPI `app`.

No other module reads environment variables or instantiates adapters of other modules.

## Testing strategy

TDD workflow and the "done" rules are in `AGENTS.md`. Structure:

- `tests/unit/<module>/`: domain and use cases. No I/O, no network. Ports are replaced by in-memory fakes (for example, `InMemoryMovieRepository`, `FakeEmbedder` with deterministic vectors, `FakeLLMClient` with canned responses).
- `tests/integration/<module>/`: adapters against real postgres/qdrant from the devcontainer, marked `@pytest.mark.integration`. They use `data/sample/omdb_sample.jsonl`.
- LLM and embedding adapters are never tested against real APIs; use recorded fixtures.
- Prefer fakes over mocks. Use mocks only to assert an interaction with an outbound port, and never mock domain objects.

## Import contracts (import-linter)

These rules are enforced with `uv run lint-imports`. The contracts are added to `pyproject.toml` in the first task of spec 001, together with the `[build-system]` that the `src/` layout needs. Reference configuration:

```toml
[tool.importlinter]
root_package = "movie_search"
include_external_packages = true

# Modules form an acyclic graph; query_understanding and catalog are independent.
[[tool.importlinter.contracts]]
name = "Capabilities dependency graph"
type = "layers"
containers = ["movie_search"]
layers = [
    "main",
    "answering",
    "search",
    "query_understanding | catalog",
    "shared",
]

# Clean Architecture layers inside each capability.
[[tool.importlinter.contracts]]
name = "Layers inside each capability"
type = "layers"
containers = [
    "movie_search.catalog",
    "movie_search.search",
    "movie_search.query_understanding",
    "movie_search.answering",
]
layers = [
    "entrypoints | infrastructure",
    "application",
    "domain",
]

# Domain stays framework-free.
[[tool.importlinter.contracts]]
name = "Domain is framework-free"
type = "forbidden"
source_modules = [
    "movie_search.catalog.domain",
    "movie_search.search.domain",
    "movie_search.query_understanding.domain",
    "movie_search.answering.domain",
    "movie_search.shared",
]
forbidden_modules = [
    "fastapi", "pydantic_settings", "sqlalchemy", "psycopg",
    "qdrant_client", "openai", "anthropic", "httpx",
]

# Modules use each other only through `application`.
[[tool.importlinter.contracts]]
name = "No access to other modules' internals"
type = "forbidden"
allow_indirect_imports = true
source_modules = ["movie_search.answering"]
forbidden_modules = [
    "movie_search.search.domain",
    "movie_search.search.infrastructure",
    "movie_search.search.entrypoints",
]
# Repeat this contract for each consumer → provider pair (search → catalog, search → query_understanding).
```

Check the exact syntax against the installed import-linter version when the contracts are added (independent layers with `|` need import-linter 2.x). Keep `forbidden_modules` in line with the dependencies the project actually uses.
