# Constitution — movie-ai-search

Non-negotiable rules. Every spec, design, task and line of code must comply with them. If a task conflicts with this document, stop and ask. Only the human amends it (see *Amendments*).

## 1. Scope
- P1 delivers: movie ingestion, semantic search (`/search`), hybrid search (vector + keyword, fused with RRF) with LLM filter extraction, RAG answers with citations (`/ask`), and an offline evaluation (recall@k, nDCG@k, latency, cost).
- Out of scope: Learning to Rank, user accounts and auth, a frontend beyond a minimal demo, microservices, event-driven messaging.
- Nothing is built unless it is in an approved spec.

## 2. Stack
Python 3.12 · uv · FastAPI · pydantic-settings · psycopg 3 (plain SQL, no ORM) · PostgreSQL 16 (full-text search) · qdrant-client · fastembed with `sentence-transformers/all-MiniLM-L6-v2` (384 dims) · pytest · ruff · import-linter.
- The LLM provider is chosen in spec 002 through an amendment.
- Any other runtime or dev dependency requires approval.
- Data-preparation libraries (the `notebooks` group: polars, aiohttp…) are never imported from `app/`.

## 3. Architecture
- Modular monolith + light hexagonal: modules `app/catalog/` and `app/search/`, each with `domain/`, `application/` and `infrastructure/`. Details in `docs/architecture.md`.
- Dependencies point inward: `domain/` and `application/` never import frameworks or providers (FastAPI, Pydantic, psycopg, qdrant-client, fastembed, LLM SDKs). import-linter enforces it.
- Ports are `typing.Protocol` classes in `application/ports.py`: `EmbeddingProvider`, `VectorStore`, `KeywordSearch`, `LLMProvider`, `MovieRepository`. A new port needs a justification in the spec's `design.md`.
- Domain models are dataclasses. Pydantic only in adapters (API schemas, settings, LLM structured output).
- Use cases return domain objects or raise domain exceptions, never HTTP status codes.
- Ranking logic (RRF fusion, filters) is pure domain code.
- `search` may use `catalog.application`, never `catalog.infrastructure`.

## 4. Tests
- Business logic follows TDD: failing test first, reviewed by the human, then minimal code, then refactor.
- Every requirement (RF) has at least one test that names it.
- Unit tests use fakes (`FakeEmbeddingProvider`, `FakeLLMProvider`, `InMemoryVectorStore`…) and never touch the network, real providers or the full dataset.
- Integration tests are marked `@pytest.mark.integration` and use the devcontainer `postgres` and `qdrant` services, with a separate test database and collection.
- LLM answer quality is measured with evals, not unit tests.
- No `Mock()` without a spec: use `create_autospec`.

## 5. LLM and data
- LLM output is validated deterministically before it is returned: schema (structured output) and citations (every cited movie must be among the retrieved ones).
- Secrets live only in `.env`: never in code, logs or git.
- The full dataset is never committed or redistributed (IMDb non-commercial terms); only `data/sample/` is versioned.

## 6. Workflow
- One spec per feature in `specs/NNN-name/`: `requirements.md` (EARS: *WHEN … THE SYSTEM SHALL …*) → clarification → `design.md` → `tasks.md`, approved by the human before any code.
- One task at a time; tasks of 20–30 min, each with its RFs and a "Done when:" line.
- Each spec closes with `validation.md`: RF by RF, the test that covers it, the result and a verdict.

## 7. Conventions
- Code, identifiers, docs and commit messages in English; Conventional Commits.
- Type hints on every public function; ruff defaults.

## Amendments
| Version | Date | Change | Reason |
|---|---|---|---|
| 1.0 | 2026-10-30 | Initial version | — |