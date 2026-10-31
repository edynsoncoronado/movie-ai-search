# Constitution — movie-ai-search

Non-negotiable rules. Every spec, design, task and line of code must comply with them. If a task conflicts with this document, stop and ask. Only the human amends it (see *Amendments*).

This document says **why** and **what never changes**. The structure (modules, ports, contracts) lives in `docs/architecture.md`; how to operate (commands, TDD steps) lives in `AGENTS.md`.

## 1. Scope
- P1 delivers: movie ingestion, semantic search (`/search`), hybrid search (vector + keyword, fused with RRF) with LLM filter extraction, RAG answers with citations (`/ask`), and an offline evaluation (recall@k, nDCG@k, latency, cost).
- Out of scope: Learning to Rank, user accounts and auth, a frontend beyond a minimal demo, microservices, event-driven messaging.
- Nothing is built unless it is in an approved spec.

## 2. Stack
Python 3.12 · uv (`src/` layout, `uv_build` backend) · FastAPI · Pydantic + pydantic-settings (adapters only) · psycopg 3 (plain SQL, no ORM) · PostgreSQL 16 (full-text search) · Qdrant + qdrant-client · fastembed with `sentence-transformers/all-MiniLM-L6-v2` (384 dims) · pytest · ruff · import-linter.
- The LLM provider is chosen in spec 002 through an amendment.
- Any other runtime or dev dependency requires approval.
- Data-preparation libraries (the `notebooks` group: polars, aiohttp…) are never imported from `src/`.

## 3. Architecture principles
- **Modular monolith**: one application, one deployment, organized as a screaming architecture (packages are business capabilities). Clean Architecture layers inside each module.
- **Dependencies point inward** and are enforced by import-linter. The contracts only change with the human's approval.
- **Ports and adapters only where I/O can change**: LLM, embeddings, vector store, database, data files.
- **Ports are task-oriented** (one job each, such as "extract filters" or "generate an answer"), never a generic `complete(prompt)`. Fakes stay trivial and prompts stay inside adapters.
- **The domain is plain Python**: dataclasses, no frameworks. Pydantic lives only in adapters (API schemas, settings, LLM structured output).
- **Use cases** return domain objects or raise domain exceptions, never HTTP status codes.
- **Ranking and validation logic** (RRF fusion, filters, citation checks) is pure domain code.
- **Each module owns its data** (tables, collections). Other modules reach it only through that module's `application` API.

## 4. Tests
- Business logic follows TDD: failing test first, reviewed by the human, then minimal code, then refactor.
- Every requirement (RF) has at least one test that names it.
- Unit tests never touch the network, real LLM providers or the full dataset.
- LLM answer quality is measured with evals, not unit tests.

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
- Only the human amends this constitution. Agents may propose a change, and edit this file only when the human explicitly asks for it.
- Every amendment bumps the version and adds a row to the table below with its date, change and reason.
- After an amendment, review the active specs in `specs/` for conflicts with the new text. Any conflict is resolved before work on that spec continues.

| Version | Date | Change | Reason |
|---|---|---|---|
| 1.0 | 2026-10-30 | Initial version | — |
