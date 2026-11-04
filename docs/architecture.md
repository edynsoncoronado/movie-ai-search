# Architecture

movie-ai-search follows **Clean Architecture** inside a **screaming architecture**: the top-level packages name what the system does (catalog, search, answering), and each one is split internally into layers with dependencies pointing inward. It is a modular monolith: one application, one deployment.

The principles behind these rules are in `docs/constitution.md`; the TDD workflow and the "done" rules are in `AGENTS.md`.

**What this document holds.** Only the stable structure: modules, dependencies, layers, composition-root rules, test levels and key decisions. Ports, types, schemas and signatures belong to the `design.md` of the spec that introduces them, and once implemented the code is the reference. The import contracts live only in `pyproject.toml`. See *Keeping this document current*.

## Package layout

```
src/movie_search/
  catalog/               # movies and their ingestion
    domain/
    application/
    infrastructure/
    entrypoints/         # optional: HTTP routers and CLI commands
  search/                # indexing, keyword and hybrid search, filter extraction
    domain/
    application/
    infrastructure/
    entrypoints/
  answering/             # RAG answers with citations
    domain/
    application/
    infrastructure/
    entrypoints/
  shared/                # minimal shared kernel
  bootstrap.py           # settings and builders that wire adapters into use cases
  main.py                # composition root: FastAPI app
  cli.py                 # composition root: CLI
tests/
  fakes/                 # in-memory fakes of the ports, shared by all unit tests
  fixtures/              # hand-written test data
  unit/<module>/
  integration/<module>/
```

- The three module packages exist from the first task of spec 001, even if `answering` stays empty until spec 003: import-linter requires every module named in a contract to exist.
- `entrypoints/` is optional: a module has it only when a spec exposes something over HTTP or the CLI.
- A new capability (for example, an `evaluation` module in spec 004) is a new top-level module, never a technical folder such as `utils/`, `services/` or `models/`.

## Modules

| Module | Responsibility | Owns |
|---|---|---|
| `catalog` | The movie data and its ingestion. The source of truth for movies. | The `catalog` schema in PostgreSQL |
| `search` | Indexing, keyword (BM25) and hybrid search, and turning a natural-language query into structured filters. | Its Qdrant collections: derived data that can always be rebuilt from the catalog |
| `answering` | Grounded answers built from search results, with citations to the movies used. | — |
| `shared` | Value objects that several modules need. Kept small. | — |

**Rules for ports** (each spec's `design.md` names them and sets their shape):
- Ports are `typing.Protocol`s defined in the `application` layer of the module that uses them.
- They exist only where I/O can change: database, data files, vector store, embedding model, LLM.
- **LLM ports are task-oriented** (for example "extract filters", "generate an answer"), never a generic `complete(prompt)`. Their adapters may share one LLM SDK client, built once in `bootstrap.py`.
- **The embedding port is separate from the LLM ports.** The embedding model and the chat model change for different reasons.
- **Index ports hide the engine.** The application passes plain text and receives identifiers with scores; tokenization, models and Qdrant details stay in the adapter.

Filter extraction lives inside `search` and is not a module of its own: its only consumer is search, and filters are a search concept.

### Dependencies between modules

```
main ─┐
      ├──▶ bootstrap ──▶ answering ──▶ search ──▶ catalog ──▶ shared
cli  ─┘
```

- **The graph is acyclic.** Lower modules never import higher ones. `main` and `cli` do not import each other.
- **Public API.** A module imports another only through its `application` public API: the names exported from `movie_search/<module>/application/__init__.py`. That file exports the use cases and the **published types** they use (entities, exceptions, constants), re-exported from its domain. Consumers never import another module's `domain`, `infrastructure` or `entrypoints`.
- **A module's `domain` imports no other capability**: only the standard library and `shared`.
- **Each module owns its storage.** No module reads another module's tables or collections. `search` builds its indexes from movies it gets through `catalog.application`, and completes search results the same way.
- **`shared` imports no capability.** If something has behavior that belongs to one capability, it lives in that capability.
- **Future `evaluation` module.** It consumes `search` and sits at the same level as `answering` (`"answering | evaluation"` in the contract).

## Layers inside a module

```
entrypoints ───┐
               ├──▶ application ──▶ domain
infrastructure ┘
```

| Layer | Contains | May import | Must not import |
|---|---|---|---|
| `domain` | Entities, value objects, pure domain functions (ranking, validation and filter rules, citation checks). | stdlib, `shared` | Any framework or I/O library; `application`, `infrastructure`, `entrypoints`; other capabilities |
| `application` | Use cases, port definitions (`typing.Protocol`), boundary DTOs (dataclasses), the public API in `__init__.py`. | `domain`, `shared`, other modules' `application` | `infrastructure`, `entrypoints`, frameworks (including `pydantic`) |
| `infrastructure` | Adapters that implement ports: PostgreSQL, Qdrant, embedding and LLM clients, file readers. | `application`, `domain`, `shared`, external libraries | `entrypoints`, other modules' `infrastructure`, `bootstrap` |
| `entrypoints` | FastAPI routers and CLI commands. They translate input/output (Pydantic request/response schemas live here) and call use cases. | `application`, `fastapi`, `pydantic` | `infrastructure`, `bootstrap`, `main`, `cli` (they receive use cases already wired) |

The libraries forbidden in `domain`, `application` and `shared` are listed in the "framework-free" contract in `pyproject.toml`; keep that list in line with the dependencies the project actually uses.

## Composition root

- **`bootstrap.py`** is the only place that defines and reads the settings (pydantic-settings, from `.env`) and builds concrete adapters.
  - It exposes **one builder per use case**, so each entry point builds only what it needs (for example, `ingest` never loads a search model).
  - Builders **import their adapters inside the function body**, so importing `bootstrap` loads no driver or model.
  - Expensive objects (models, SDK clients) are built **once per process** and shared between builders.
- **`main.py`** creates the FastAPI `app` and mounts each router with use cases from the builders. **`cli.py`** does the same for the CLI commands.
- **Routers and commands are built with factories** that receive the use case (or a builder). They never import `main`, `cli` or `bootstrap`; a `Depends()` defined in `main.py` would break the dependency graph.

No other module reads environment variables or instantiates adapters.

## Testing strategy

| Level | What | How |
|---|---|---|
| `tests/unit/<module>/` | Domain and use cases | No I/O, no network, no models. Ports are replaced by in-memory fakes from `tests/fakes/`. |
| `tests/unit/<module>/` | Entry points | FastAPI `TestClient` or the CLI parser, with a fake or `create_autospec` of the use case: only the translation is tested. |
| `tests/integration/<module>/` | Adapters and wiring | Marked `@pytest.mark.integration`. They run against the devcontainer's real `postgres` and `qdrant`, with a separate test database and collection, and with the models cached in the devcontainer. |
| Evals (spec 004) | Retrieval and LLM answer quality | Labeled query set and metrics, not unit tests. |

- No unit test imports `movie_search.main` or calls a `bootstrap` builder: both load drivers or models.
- LLM adapters are never tested against real APIs; use recorded fixtures.
- Prefer fakes over mocks. Use mocks only to assert an interaction with an outbound port, always with `create_autospec`, and never mock domain objects.

## Import contracts (import-linter)

The contracts are defined only in `pyproject.toml` (`[tool.importlinter]`) and enforced with `uv run lint-imports` (pre-commit and CI). Spec 001 introduces them in its first task.

| Rule | Contract |
|---|---|
| Domain → Application, Domain → Adapters, Application → Adapters: forbidden | Clean Architecture layers inside each capability |
| Adapters → Application, Adapters → Domain, Application → Domain: allowed | Clean Architecture layers inside each capability |
| `entrypoints` ↔ `infrastructure`: forbidden in both directions | Clean Architecture layers inside each capability (independent layers) |
| No upward imports between modules; no adapter imports `bootstrap` | Capabilities dependency graph |
| No frameworks in `domain`, `application` or `shared` | Domain, application and shared are framework-free |
| Cross-module access only through `application` | search uses catalog only through catalog.application; answering uses search and catalog only through their application |
| A domain does not depend on another capability | Domains import no other capability |

When a module is added, it is added to the contracts in the same change. The contracts only change with the human's approval.

## Key decisions

Append-only: a decision that stops applying is marked "superseded by #N", never deleted.

| # | Decision | Discarded alternative | Reason |
|---|---|---|---|
| 1 | Modular monolith | Microservices, event-driven | One developer, ~5 h/week; no requirement asks to scale parts separately |
| 2 | Modules by capability (`catalog`, `search`, `answering`) | Folders by technical layer | Screaming architecture: the layout says what the system does |
| 3 | Filter extraction inside `search` | Separate `query_understanding` module | Its only consumer is search, and filters are a search domain concept |
| 4 | Task-oriented LLM ports | Generic `LLMClient.complete(prompt)` | Trivial fakes; prompts encapsulated in adapters |
| 5 | Dataclasses in the domain, Pydantic only in adapters | Pydantic everywhere | The domain depends on no library |
| 6 | Two composition roots sharing `bootstrap.py` | Wiring only in `main.py` | Ingestion and evaluation run from the CLI, without HTTP |
| 7 | Router factories | `Depends()` providers in `main.py` | Entry points do not import the composition root |
| 8 | Each module owns its storage | Search queries catalog's tables | Modules stay replaceable; no coupling through the database |
| 9 | import-linter contracts | Manual review | The dependency rule is checked on every commit and in CI |
| 10 | BM25 on Qdrant sparse vectors (fastembed `Qdrant/bm25` + IDF modifier) | PostgreSQL full-text search (`ts_rank`) | `ts_rank` is not BM25 (no IDF, no length normalization); one engine serves both retrievers in hybrid search |
| 11 | PostgreSQL catalog as the source of truth; Qdrant collections are derived | Qdrant payload as the only store | Several indexes (sparse, dense) are built from the same clean data; reindexing never re-parses the source file; ingestion is an idempotent upsert by `imdb_id` |
| 12 | Full rebuild with an atomic alias swap | Updating or recreating the collection in place | `/search` keeps working while `index` runs, and a failed rebuild leaves the previous index untouched |
| 13 | Filters applied inside each retriever (Qdrant payload filters) | Filtering after RRF fusion | Filtering after fusion shrinks the top-k and loses relevant results |
| 14 | This document holds only stable structure; spec-level detail lives in each `design.md` and in the code; contracts only in `pyproject.toml` | One document with ports, types and examples | Spec-level detail drifted with every spec (constitution 1.3) |
| 15 | One builder per use case, with deferred adapter imports | A single `bootstrap.build()` that wires everything | Each entry point loads only what it needs, and `Settings` stays unit-testable |

## Keeping this document current

A spec changes this document only when it changes the stable structure: a new module, a new dependency between modules, new storage, a new composition-root or testing rule, or a key decision. In that case (constitution §6):
1. its `design.md` lists the change under *Architecture changes*;
2. its `tasks.md` includes updating this document;
3. its `validation.md` confirms this document is still true.

New ports, types, use cases, schemas or settings are not architecture changes: they stay in the spec's `design.md`.
