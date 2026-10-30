# movie-ai-search

Natural-language movie search API: semantic + keyword (hybrid) search over ~47k OMDb movies, with LLM filter extraction and RAG answers with citations. Built with spec-driven development (SDD) + TDD + Clean Architecture, organized as a screaming architecture.

## Read first
1. `docs/constitution.md`: non-negotiable rules.
2. `docs/architecture.md`: modules, layers, ports and import contracts.
3. The active spec in `specs/NNN-feature/`, and **only** the task you are given from its `tasks.md`.

## Environment
- Everything runs inside the devcontainer: services `app`, `postgres`, `qdrant`. Use the hostnames `postgres` and `qdrant`, never `localhost`.
- Python 3.12 + uv. The venv lives in `/opt/venv`; always run tools with `uv run`.
- Config comes from `.env` (template: `.env.example`). Never print or commit `.env`.
- Data: tests use `data/sample/omdb_sample.jsonl` (200 movies). The full dataset is at `MOVIES_DATA_PATH` and is not in git (see `data/README.md`).

## Commands
- Install: `uv sync --all-groups`
- Fast tests: `uv run pytest -m "not integration"`
- All tests (postgres + qdrant up): `uv run pytest`
- Architecture: `uv run lint-imports`
- Lint: `uv run ruff check . && uv run ruff format --check .`
- API: `uv run uvicorn movie_search.main:app --reload --host 0.0.0.0`

> pytest, ruff and import-linter are installed in the first task of spec 001. If a command fails because a tool is missing, say so: do not install it yourself.

## Architecture (summary)
- **Screaming layout**: top-level packages are business capabilities, not technical layers: `src/movie_search/{catalog, search, query_understanding, answering}/`, plus a minimal `shared/` kernel. A new capability is a new top-level module; never add `utils/`, `services/`, `models/` or `helpers/` packages.
- **Layers inside each module**: `domain/` ← `application/` ← `infrastructure/` and `entrypoints/`. Dependencies point inward only.
- `domain/` is pure Python: no I/O and no frameworks (FastAPI, SQLAlchemy, psycopg, qdrant-client, LLM/embedding SDKs, pydantic-settings).
- `application/` holds use cases and defines the ports they need (`typing.Protocol`).
- `infrastructure/` implements those ports.
- `entrypoints/` (HTTP routers, CLI) only call use cases.
- Modules talk to each other only through another module's `application` public API (what its `__init__.py` exports). Never import another module's `domain` internals, `infrastructure` or `entrypoints`.
- Wiring (choosing adapters, reading settings) happens only in `movie_search/main.py`, the composition root.
- import-linter enforces these rules. If a contract fails, fix the design; never loosen the contract without asking.

## How we work (TDD)
Business logic (domain, use cases, filters, ranking) follows red → green → refactor:
1. **Red**: write **only the tests** for the task, run them, and show they fail for the expected reason (a failing assertion or missing behavior, not an import or syntax error). **Stop** until I review the tests.
2. **Green**: after approval, write the minimum code that makes them pass. **Do not edit approved tests.** If one looks wrong, say why and stop.
3. **Refactor**: improve the code with all tests green. No new behavior without a new failing test first.

Mechanical tasks (DTOs, config, wiring): tests and code in one step.

Tests:
- Layout mirrors the modules: `tests/unit/<module>/` (no I/O, no network, fast) and `tests/integration/<module>/` (real postgres/qdrant, marked `@pytest.mark.integration`).
- Unit tests use in-memory fakes of the ports. Use mocks only to check interactions with outbound ports, and never mock domain objects.
- LLM and embedding adapters are tested with fakes or recorded fixtures, never with real APIs.

Do not commit: I review and commit each task (Conventional Commits).

## Done = verified
A task is done only after green/refactor; the red checkpoint is not "done". Then run:
`uv run pytest -m "not integration" && uv run lint-imports && uv run ruff check . && uv run ruff format --check .`
All green → mark the task in `tasks.md`, list the RFs it covers, and **stop**. Do not start the next task.

## Never without asking
- Add, remove or upgrade dependencies.
- Edit `docs/constitution.md`, any `requirements.md`, or an approved spec.
- Change or relax import-linter contracts or the module layout in `docs/architecture.md`.
- Call real LLM or embedding APIs from tests, or spend API credits.
- Touch `notebooks/` or `data/` (data preparation, outside the app).
- Push, rebase or rewrite git history.
