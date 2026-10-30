# Architecture

movie-ai-search follows **Clean Architecture** inside a **screaming architecture**: the top-level packages name what the system does (catalog, search, answering), and each one is split internally into layers with dependencies pointing inward. It is a modular monolith: one application, one deployment.

The principles behind these rules are in `docs/constitution.md`; the TDD workflow and the "done" rules are in `AGENTS.md`.

## Package layout

```
src/movie_search/
  catalog/               # movies and their ingestion
    domain/
    application/
    infrastructure/
    entrypoints/         # CLI command: ingest
  search/                # filter extraction, indexing and hybrid search
    domain/
    application/
    infrastructure/
    entrypoints/         # /search router, CLI command: index
  answering/             # RAG answers with citations
    domain/
    application/
    infrastructure/
    entrypoints/         # /ask router
  shared/                # minimal shared kernel
  bootstrap.py           # builds settings, adapters and use cases
  main.py                # composition root: FastAPI app
  cli.py                 # composition root: CLI (ingest, index, eval)
tests/
  fakes/                 # in-memory fakes of the ports, shared by all unit tests
  unit/<module>/
  integration/<module>/
```

- The three module packages exist from the first task of spec 001, even if `answering` stays empty until spec 002: import-linter requires every module named in a contract to exist.
- `entrypoints/` is optional: a module has it only when a spec exposes something over HTTP or the CLI.
- A new capability (for example, an `evaluation` module for nDCG@k / recall@k in spec 003) is a new top-level module, never a technical folder such as `utils/`, `services/` or `models/`.

## Modules

| Module | Responsibility | Main concepts | Ports (defined in `application/`) |
|---|---|---|---|
| `catalog` | Owns the movie data and its ingestion from OMDb JSONL. | `Movie`, `ImportMovies` | `MovieRepository` (postgres), `MovieSource` (JSONL file) |
| `search` | Turns a natural-language query into structured filters, indexes movies and runs hybrid search: vector + keyword, fused with RRF, then filtered. | `SearchFilters`, `SearchQuery`, `ScoredMovie`, `rrf_fuse`, `IndexMovies`, `SearchMovies` | `Embedder`, `VectorIndex` (qdrant), `KeywordIndex` (postgres), `FilterExtractor` (LLM) |
| `answering` | Builds a grounded answer from search results, with citations to the movies used. | `Answer`, `Citation`, `AnswerQuestion` | `AnswerGenerator` (LLM) |
| `shared` | Value objects that several modules need (e.g. `MovieId`, `Year`). | — | — |

The ports' names are guidance; the spec for each feature sets their final shape. Two design rules apply to all of them:

- **LLM ports are task-oriented.** `FilterExtractor.extract(query) -> SearchFilters` and `AnswerGenerator.generate(question, movies) -> Answer`, never a generic `complete(prompt)`. Their adapters may share one LLM SDK client, which `bootstrap.py` creates once.
- **`Embedder` is separate from the LLM ports.** The embedding model and the chat model change for different reasons.

Filter extraction lives inside `search` and is not a module of its own. Its only consumer is search, and `SearchFilters` is a search concept that the search domain uses directly (filter rules, `VectorIndex.search(filters)`).

### Dependencies between modules

```
main ─┐
      ├──▶ bootstrap ──▶ answering ──▶ search ──▶ catalog ──▶ shared
cli  ─┘
```

- **The graph is acyclic.** Lower modules never import higher ones. `main` and `cli` do not import each other.
- **Public API.** A module imports another only through its `application` public API: the names exported from `movie_search/<module>/application/__init__.py`. That file exports the use cases and the **published types** they return, re-exported from its domain (e.g. `from movie_search.search.domain.models import ScoredMovie`). Consumers never import another module's `domain`, `infrastructure` or `entrypoints`.
- **A module's `domain` imports no other capability**: only the standard library and `shared`.
- **Each module owns its storage.** `catalog` owns the movies table. `search` owns its Qdrant collection and its own keyword-index table (populated by `IndexMovies`). No module reads another module's tables or collections.
- **`shared` imports no capability.** Keep it small: if something has behavior that belongs to one capability, it lives in that capability.
- **Future `evaluation` module.** It consumes `search` and sits at the same level as `answering` (`"answering | evaluation"` in the contract).

## Layers inside a module

```
entrypoints ───┐
               ├──▶ application ──▶ domain
infrastructure ┘
```

| Layer | Contains | May import | Must not import |
|---|---|---|---|
| `domain` | Entities, value objects, pure domain functions (e.g. RRF fusion, filter rules, citation checks). | stdlib, `shared` | Any framework or I/O library; `application`, `infrastructure`, `entrypoints`; other capabilities |
| `application` | Use cases, port definitions (`typing.Protocol`), boundary DTOs (dataclasses), the public API in `__init__.py`. | `domain`, `shared`, other modules' `application` | `infrastructure`, `entrypoints`, frameworks (including `pydantic`) |
| `infrastructure` | Adapters that implement ports: postgres, qdrant, embedding and LLM clients, JSONL readers. | `application`, `domain`, `shared`, external libraries | `entrypoints`, other modules' `infrastructure`, `bootstrap` |
| `entrypoints` | FastAPI routers and CLI commands. They translate input/output (Pydantic request/response schemas live here) and call use cases. | `application`, `fastapi`, `pydantic` | `infrastructure`, `bootstrap`, `main`, `cli` (they receive use cases already wired) |

Libraries forbidden in `domain`, `application` and `shared`: `fastapi`, `pydantic`, `pydantic_settings`, `psycopg`, `qdrant_client`, `fastembed`, `openai`, `anthropic`, `httpx`. Keep this list in line with the dependencies the project actually uses.

## Composition root

- **`bootstrap.py`** is the only place that:
  - defines and reads the settings (pydantic-settings, from `.env`);
  - builds the concrete adapters, including the LLM SDK client, once;
  - injects them into the use cases and returns them.
- **`main.py`** creates the FastAPI `app` and mounts each router with the use cases from `bootstrap.py`.
- **`cli.py`** does the same for the CLI commands.

No other module reads environment variables or instantiates adapters.

Routers are built with a **factory** that receives the use case. A router never imports `main` or `bootstrap`; a `Depends()` defined in `main.py` would break the dependency graph.

```python
# search/entrypoints/http.py
def build_router(search_movies: SearchMovies) -> APIRouter:
    router = APIRouter()

    @router.get("/search")
    def search(q: str, limit: int = 10) -> SearchResponse:
        return SearchResponse.from_domain(search_movies.execute(q, limit))

    return router


# main.py
container = bootstrap.build()
app = FastAPI()
app.include_router(search_http.build_router(container.search_movies))
```

## Testing strategy

| Level | What | How |
|---|---|---|
| `tests/unit/<module>/` | Domain and use cases | No I/O, no network. Ports are replaced by in-memory fakes from `tests/fakes/` (`InMemoryMovieRepository`, `FakeEmbedder` with deterministic vectors, `InMemoryVectorIndex`, `FakeFilterExtractor` and `FakeAnswerGenerator` with canned responses). |
| `tests/unit/<module>/` | Entry points | FastAPI `TestClient` with a router built from a fake or `create_autospec` of the use case: only the translation is tested. |
| `tests/integration/<module>/` | Adapters | Marked `@pytest.mark.integration`. They run against the devcontainer's real `postgres` and `qdrant`, with a separate test database and collection, using `data/sample/omdb_sample.jsonl`. The local fastembed embedder may run here (the model is cached in the devcontainer). |
| Evals (spec 003) | LLM answer quality | Labeled query set and metrics, not unit tests. |

- LLM adapters are never tested against real APIs; use recorded fixtures.
- Prefer fakes over mocks. Use mocks only to assert an interaction with an outbound port, always with `create_autospec`, and never mock domain objects.

## Import contracts (import-linter)

These rules are enforced with `uv run lint-imports`. They are added to `pyproject.toml` in the first task of spec 001, together with the build system that the `src/` layout needs:

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

**What each contract guarantees**

| Rule | Contract |
|---|---|
| Domain → Application, Domain → Adapters, Application → Adapters: forbidden | Clean Architecture layers inside each capability |
| Adapters → Application, Adapters → Domain, Application → Domain: allowed | Clean Architecture layers inside each capability |
| `entrypoints` ↔ `infrastructure`: forbidden in both directions | Clean Architecture layers inside each capability (`\|` = independent) |
| No upward imports between modules; no adapter imports `bootstrap` | Capabilities dependency graph |
| No frameworks in `domain`, `application` or `shared` | Domain, application and shared are framework-free |
| Cross-module access only through `application` | the two "uses … only through" contracts |
| A domain does not depend on another capability | Domains import no other capability |

**Verification.** The contracts were tested with import-linter 2.5.2 on an empty skeleton of this layout:
- All legitimate imports pass, including a published type re-exported from `search.application`.
- 13 forbidden imports are all caught.

When a module is added, it needs to be added to the contracts in the same change.

## Key decisions

| # | Decision | Discarded alternative | Reason |
|---|---|---|---|
| 1 | Modular monolith | Microservices, event-driven | One developer, ~5 h/week; no requirement asks to scale parts separately |
| 2 | Modules by capability (`catalog`, `search`, `answering`) | Folders by technical layer | Screaming architecture: the layout says what the system does |
| 3 | Filter extraction inside `search` | Separate `query_understanding` module | Its only consumer is search, and `SearchFilters` is a search domain concept |
| 4 | Task-oriented LLM ports | Generic `LLMClient.complete(prompt)` | Trivial fakes; prompts encapsulated in adapters |
| 5 | Dataclasses in the domain, Pydantic only in adapters | Pydantic everywhere | The domain depends on no library |
| 6 | Two composition roots sharing `bootstrap.py` | Wiring only in `main.py` | Ingestion and evaluation run from the CLI, without HTTP |
| 7 | Router factories | `Depends()` providers in `main.py` | Entry points do not import the composition root |
| 8 | Each module owns its storage | Search queries catalog's tables | Modules stay replaceable; no coupling through the database |
| 9 | import-linter contracts | Manual review | The dependency rule is checked on every commit and in CI |
