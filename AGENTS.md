# movie-ai-search

Natural-language movie search API: semantic + keyword (hybrid) search over ~47k OMDb movies, with LLM filter extraction and RAG answers with citations. Built with spec-driven development (SDD) + TDD + Clean Architecture, organized as a screaming architecture.

## Read first
1. `docs/constitution.md`: non-negotiable rules.
2. `docs/architecture.md`: modules, layers, ports, composition root, test structure and import contracts.
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
- CLI (ingest, index, eval): `uv run python -m movie_search.cli --help`

> pytest, ruff and import-linter are installed in the first task of spec 001. If a command fails because a tool is missing, say so: do not install it yourself.

## Architecture: rules you must never break
Full rules and the reasons behind them are in `docs/architecture.md`.
- Top-level packages are business capabilities: `catalog`, `search`, `answering`, plus a minimal `shared` kernel. Never add `utils/`, `services/`, `models/` or `helpers/` packages.
- Inside each module: `domain/` ← `application/` ← `infrastructure/` and `entrypoints/`. Dependencies point inward only. `domain/` and `application/` import no framework or provider SDK (not even `pydantic`).
- Modules talk to each other only through another module's `application` public API (its `__init__.py`).
- Wiring happens only in `bootstrap.py`, used by the composition roots `main.py` (API) and `cli.py` (CLI).
- import-linter enforces these rules. If a contract fails, fix the design; never loosen a contract without asking.

## How we work (TDD)
Business logic (domain, use cases, filters, ranking) follows red → green → refactor:
1. **Red**: write **only the tests** for the task, plus empty stubs (signatures that `raise NotImplementedError`) for the code they call, so they fail on behavior, not on imports or syntax. Run them, show the failures, and **stop** until I review the tests.
2. **Green**: after approval, write the minimum code that makes them pass. **Do not edit approved tests.** If one looks wrong, say why and stop.
3. **Refactor**: improve the code with all tests green. No new behavior without a new failing test first.

Mechanical tasks (DTOs, config, wiring): tests and code in one step.

Test layout, fakes and when to use mocks: `docs/architecture.md` § *Testing strategy*.

Do not commit: I review and commit each task (Conventional Commits).

## Done = verified
A task is done only after green/refactor; the red checkpoint is not "done". Then run:
`uv run pytest -m "not integration" && uv run lint-imports && uv run ruff check . && uv run ruff format --check .`
All green → mark the task in `tasks.md`, list the RFs it covers, and **stop**. Do not start the next task.

## Never without asking
- Add, remove or upgrade dependencies.
- Edit `docs/constitution.md`, any `requirements.md`, or an approved spec.
- Change or relax import-linter contracts or the module layout in `docs/architecture.md`.
- Call real LLM APIs from tests, or spend API credits.
- Touch `notebooks/` or `data/` (data preparation, outside the app).
- Push, rebase or rewrite git history.