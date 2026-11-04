# 001 · Catalog ingestion and keyword search (BM25) — Tasks

How to work through this list:
- Run one task at a time, following `AGENTS.md`.
- **TDD** tasks: red (tests + stubs) → **stop for review** → green → refactor. When the tests are integration tests, red runs them against the real services (`uv run pytest -m integration <path>`) and they must fail on behavior (`NotImplementedError`), not on connection or import errors.
- **Mechanical** tasks: tests and code in one step.
- Names, signatures, schema and settings come from `design.md`; test names carry their RF (`test_rfN_…`).

**Gate** (the AGENTS.md "Done = verified" command):
`uv run pytest -m "not integration" && uv run lint-imports && uv run ruff check . && uv run ruff format --check .`

## Checklist

- [x] T01 · Project setup (Mechanical)
- [x] T02 · Catalog domain: parsing and validation (TDD), RF2, RF3
- [ ] T03 · Catalog application: import and read use cases (TDD), RF1, RF2, RF4
- [ ] T04 · Catalog infrastructure: JSONL source and PostgreSQL repository (TDD), RF1, RF2, RF4, RF7, RF10
- [ ] T05 · Catalog entrypoint: `ingest` command, Settings, CLI root (Mechanical), RF1, RF2
- [ ] T06 · Search domain: keyword text, query, ranking (TDD), RF6, RF7, RF8
- [ ] T07 · Search application: `IndexMovies`, `SearchMovies` (TDD), RF5, RF6, RF7, RF9, RF10
- [ ] T08 · Search infrastructure: diacritics folding and `QdrantKeywordIndex` (TDD), RF5, RF6, RF7, RF9, RF10
- [ ] T09 · Search entrypoints: `/search` router and `index` command (Mechanical), RF5, RF7, RF8, RF9, RF10
- [ ] T10 · End-to-end wiring: bootstrap, `main.py`, `cli.py` (Mechanical), RF1, RF5, RF7, RNF1
- [ ] T11 · Manual validation on the full dataset (human), DoD 1–6

---

## T01 · Project setup
- **Type**: Mechanical
- **RFs / RNFs**: RNF2 (the gate and the `integration` marker)
- **Depends on**: none
- **Before starting (human)**: approve the dependency list in `design.md` § *Dependencies*:
  - runtime: `fastapi`, `pydantic-settings`, `psycopg[binary]`, `qdrant-client`, `fastembed`, `uvicorn`;
  - dev: `pytest`, `ruff`, `import-linter`, `pre-commit`, `httpx`.
  - Nothing is installed before the human approves.
- **Files**:
  - `pyproject.toml`:
    - `[build-system]` with `uv_build` and `[tool.uv.build-backend] module-name = "movie_search"`;
    - the dependencies;
    - `[tool.pytest.ini_options]` with `testpaths = ["tests"]` and the `integration` marker;
    - `[tool.ruff]` with `src = ["src", "tests"]` and `notebooks/` excluded;
    - the build system and the 6 `[tool.importlinter]` contracts copied unchanged from `design.md` § *Import contracts* (from then on, `pyproject.toml` is their only source).
  - `uv.lock`.
  - Skeleton under `src/movie_search/`:
    - `__init__.py`;
    - `catalog/{domain,application,infrastructure,entrypoints}/__init__.py`;
    - `search/{domain,application,infrastructure,entrypoints}/__init__.py`;
    - `answering/{domain,application,infrastructure}/__init__.py`;
    - `shared/__init__.py`;
    - empty `bootstrap.py`, `main.py` and `cli.py`.
  - Tests: `tests/{unit/catalog,unit/search,integration/catalog,integration/search,fakes,fixtures}/` and `tests/test_smoke.py`.
  - `.env.example`: the new variables from `design.md` § *Settings*, including `FASTEMBED_CACHE_DIR=/root/.cache/huggingface/fastembed`, which is the `hf-cache` volume; translate the remaining Spanish comment.
  - `.pre-commit-config.yaml`: three `local` hooks (`uv run ruff check .`, `uv run lint-imports`, `uv run pytest -m "not integration"`).
- **Tests to write first**:
  - `test_smoke.py::test_package_imports`: `import movie_search`.
- **Done when**:
  - `uv sync --all-groups` succeeds;
  - `uv run lint-imports` reports 6 contracts kept on the empty skeleton;
  - `uv run pre-commit run --all-files` passes;
  - the gate passes.

## T02 · Catalog domain: parsing and validation
- **Type**: TDD
- **RFs**: RF2, RF3
- **Depends on**: T01
- **Files**:
  - `src/movie_search/catalog/domain/models.py`: `Movie`, `SourceLine`, `SkipReason`, `SkippedRecord`;
  - `src/movie_search/catalog/domain/parsing.py`: `parse_year`, `parse_minutes`, `parse_int`, `parse_float`, `split_list`, `parse_languages`, `parse_line`;
  - `src/movie_search/catalog/domain/errors.py`: `SourceUnavailable`, `CatalogUnavailable`;
  - `tests/fixtures/omdb_edge_cases.jsonl`;
  - `tests/unit/catalog/test_parsing.py`, `tests/unit/catalog/test_parse_line.py`.
- **Tests to write first**:
  - RF3, table-driven:
    - `test_rf3_na_and_empty_are_missing`: `"N/A"`, `""` and `"  "` → `None` or `()`;
    - `test_rf3_strings_are_trimmed`: `"  x  "` → `"x"`;
    - `test_rf3_year_first_four_digits`: `"2025–"` → 2025; `"1994"` → 1994; `"c. 1999"` and garbage → `None`;
    - `test_rf3_runtime_minutes`: `"104 min"` → 104; garbage → `None`;
    - `test_rf3_votes_with_thousands_separator`: `"20,678"` → 20678;
    - `test_rf3_rating_float`: `"7.8"` → 7.8;
    - `test_rf3_lists_split_trimmed_and_drop_empty`;
    - `test_rf3_language_drops_none`: `"None"` → `()`; `"None, English"` → `("English",)`.
  - RF2, from fixture lines:
    - one test per reason: `test_rf2_invalid_record_bad_json`, `test_rf2_invalid_record_raw_not_object`, `test_rf2_invalid_record_not_utf8` (`text=None`), `test_rf2_missing_imdb_id` (missing, `null`, empty, `"tt123"`), `test_rf2_invalid_response`, `test_rf2_not_a_movie`, `test_rf2_missing_title`, `test_rf2_missing_plot`;
    - `test_rf2_precedence`: `Response=False` + no plot → `invalid_response`; bad `imdb_id` + `Response=False` → `missing_imdb_id`;
    - `test_rf2_uses_top_level_imdb_id_and_ignores_raw_imdbID`;
    - `test_rf3_full_sample_record_maps_every_field`, using a record copied from the sample.
- **Done when**: every case above is green, `catalog.domain` imports only the stdlib, and the gate passes.

## T03 · Catalog application: import and read use cases
- **Type**: TDD
- **RFs**: RF1, RF2, RF4 (provides `ListMovies` for RF5 and `GetMovies` for RF7)
- **Depends on**: T02
- **Files**:
  - `src/movie_search/catalog/application/ports.py`: `MovieSource`, `MovieRepository`, `UpsertResult`;
  - `src/movie_search/catalog/application/import_movies.py`: `ImportMovies`, `ImportReport`, `ImportInterrupted`;
  - `src/movie_search/catalog/application/queries.py`: `ListMovies`, `GetMovies`;
  - `src/movie_search/catalog/application/__init__.py`: the public API listed in `design.md`;
  - `tests/fakes/catalog.py`:
    - `InMemoryMovieSource`, with a flag that makes it raise `SourceUnavailable`;
    - `InMemoryMovieRepository`, with a `fail_after_batches` flag;
  - `tests/unit/catalog/test_import_movies.py`, `tests/unit/catalog/test_queries.py`.
- **Tests to write first**:
  - **Counts and skips**:
    - `test_rf2_report_counts_per_reason`;
    - `test_rf2_warning_logged_per_skip` (`caplog`: line, `imdb_id` or `-`, reason);
    - `test_rf1_blank_lines_neither_read_nor_skipped`.
  - **Limit**:
    - `test_rf1_limit_counts_inserted_and_updated`;
    - `test_rf1_limit_3_stores_exactly_3`;
    - `test_rf1_limit_spanning_two_batches_stores_exact_total`.
  - **Upsert**:
    - `test_rf4_last_record_wins_within_file`;
    - `test_rf4_reimport_counts_updated`.
  - **Errors**:
    - `test_rf1_source_unavailable_writes_nothing`;
    - `test_rf1_catalog_failure_on_batch_1_raises_import_interrupted_with_zero_counts`;
    - `test_rf1_catalog_failure_on_batch_2_raises_import_interrupted_with_batch_1_counts`.
  - **Queries**:
    - `test_list_movies_ordered_by_imdb_id`;
    - `test_get_movies_omits_unknown_ids`.
- **Done when**: every case above is green over the fakes, `lint-imports` is green, and the gate passes.

## T04 · Catalog infrastructure: JSONL source and PostgreSQL repository
- **Type**: TDD (red: integration tests against the real postgres, with stub adapters)
- **RFs**: RF1, RF2, RF4, RF7, RF10
- **Depends on**: T03
- **Files**:
  - `src/movie_search/catalog/infrastructure/jsonl_source.py`;
  - `src/movie_search/catalog/infrastructure/postgres_repository.py`;
  - `src/movie_search/catalog/infrastructure/schema.sql`, exactly as in `design.md`;
  - `tests/integration/conftest.py`: creates the `movies_test` database from `TEST_DATABASE_URL` and truncates the table per test;
  - `tests/integration/catalog/test_jsonl_source.py`, `tests/integration/catalog/test_postgres_repository.py`.
- **Tests to write first** (all `@pytest.mark.integration`):
  - **`JsonlMovieSource`**:
    - `test_rf1_source_reads_sample_200_lines`;
    - `test_rf2_source_invalid_utf8_line_has_text_none` (bytes written to `tmp_path`);
    - `test_rf1_source_missing_file_raises_source_unavailable`;
    - `test_rf1_source_directory_raises_source_unavailable`.
  - **`PostgresMovieRepository`**:
    - `test_ensure_schema_is_idempotent`;
    - `test_rf4_first_upsert_inserted_second_updated`;
    - `test_rf4_repeated_id_in_batch_last_wins`;
    - `test_rf3_arrays_and_nulls_round_trip`;
    - `test_iter_all_ordered_by_imdb_id`;
    - `test_rf7_get_many_omits_unknown_ids`;
    - `test_rf7_get_many_missing_table_returns_empty`;
    - `test_rf10_unreachable_database_raises_catalog_unavailable`.
- **Done when**: the integration tests are green, and `uv run pytest -m integration tests/integration/catalog` and the gate pass.

## T05 · Catalog entrypoint: `ingest` command, Settings, CLI root
- **Type**: Mechanical
- **RFs**: RF1, RF2
- **Depends on**: T04
- **Files**:
  - `src/movie_search/catalog/entrypoints/cli.py`: `register(subparsers, import_movies_factory, default_path)`;
  - `src/movie_search/bootstrap.py`: `Settings` with every field in `design.md` § *Settings*, and `build_import_movies()`, which calls `ensure_schema`. Builders import their adapters inside the function body (deferred imports, `design.md` § *Composition root*);
  - `src/movie_search/cli.py`: the `argparse` root and `logging.basicConfig`;
  - `tests/unit/catalog/test_ingest_cli.py`, `tests/unit/test_settings.py`.
- **Tests to write first**:
  - **Unit, with `create_autospec(ImportMovies)`**:
    - `test_rf1_ingest_explicit_path`;
    - `test_rf1_ingest_default_path_from_settings`;
    - `test_rf1_ingest_no_path_no_env_exit_2`;
    - `test_rf1_ingest_bad_limit_exit_2` (parametrized `0`, `-1`, `abc`);
    - `test_rf1_ingest_source_unavailable_exit_1`;
    - `test_rf1_ingest_schema_failure_one_line_error_no_report_exit_1` (the factory raises `CatalogUnavailable`);
    - `test_rf1_ingest_interrupted_prints_partial_report_exit_1`;
    - `test_rf2_ingest_report_format` (reasons in RF2 order, zeros left out).
  - **Settings and bootstrap** (unit):
    - `test_settings_defaults`;
    - `test_settings_requires_database_and_qdrant_urls`;
    - `test_rnf2_importing_bootstrap_loads_no_driver` (`fastembed`, `psycopg` and `qdrant_client` are not in `sys.modules` after `import movie_search.bootstrap`).
- **Done when**:
  - `uv run python -m movie_search.cli ingest data/sample/omdb_sample.jsonl` prints `Read: 200`, `Inserted: 200`;
  - a second run prints `Updated: 200`;
  - the gate passes.

## T06 · Search domain: keyword text, query, ranking
- **Type**: TDD
- **RFs**: RF6, RF7, RF8
- **Depends on**: T01
- **Files**:
  - `src/movie_search/search/domain/models.py`: `IndexableMovie`, `KeywordDocument`, `KeywordHit`, `MovieSummary`, `SearchResult`;
  - `src/movie_search/search/domain/keyword_text.py`;
  - `src/movie_search/search/domain/query.py`: `SearchQuery`, the constants and `InvalidSearchQuery`;
  - `src/movie_search/search/domain/ranking.py`: `rank`;
  - `src/movie_search/search/domain/errors.py`: `SearchUnavailable`;
  - `tests/unit/search/test_keyword_text.py`, `tests/unit/search/test_query.py`, `tests/unit/search/test_ranking.py`.
- **Tests to write first**:
  - **`keyword_text`**:
    - `test_rf6_title_written_twice`;
    - `test_rf6_parts_in_order_title_directors_actors_genres_plot`;
    - `test_rf6_missing_parts_left_out`.
  - **`SearchQuery`**:
    - `test_rf7_query_trimmed`;
    - `test_rf8_empty_or_blank_query_rejected`;
    - `test_rf8_query_500_ok_501_rejected` (after trimming);
    - `test_rf8_limit_bounds` (0 and 51 rejected; 1 and 50 accepted);
    - `test_rf7_default_limit_10`.
  - **`rank`**:
    - `test_rf7_rank_by_score_desc`;
    - `test_rf7_equal_scores_sorted_by_imdb_id`.
- **Done when**: every case above is green, `search.domain` imports only the stdlib, and the gate passes.

## T07 · Search application: `IndexMovies`, `SearchMovies`
- **Type**: TDD
- **RFs**: RF5, RF6, RF7, RF9, RF10
- **Depends on**: T03, T06
- **Files**:
  - `src/movie_search/search/application/ports.py`: `KeywordIndex`;
  - `src/movie_search/search/application/index_movies.py`: `IndexMovies`, `IndexReport`;
  - `src/movie_search/search/application/search_movies.py`;
  - `src/movie_search/search/application/__init__.py`: the public API listed in `design.md`;
  - `tests/fakes/search.py`: `InMemoryKeywordIndex` (term-match scoring, an `unavailable` flag, keeps the last rebuild);
  - `tests/unit/search/test_index_movies.py`, `tests/unit/search/test_search_movies.py`.
- **Tests to write first** (catalog use cases built over `InMemoryMovieRepository`):
  - **`IndexMovies`**:
    - `test_rf5_rebuild_receives_one_document_per_movie`;
    - `test_rf6_documents_use_keyword_text`;
    - `test_rf5_empty_catalog_indexes_0`.
  - **`SearchMovies`**:
    - `test_rf7_results_ordered_and_limited`;
    - `test_rf7_results_completed_from_catalog`;
    - `test_rf7_hit_missing_from_catalog_dropped_with_warning`;
    - `test_rf9_empty_index_returns_empty`;
    - `test_rf10_index_unavailable_propagates`;
    - `test_rf10_catalog_unavailable_becomes_search_unavailable`.
- **Done when**:
  - every case above is green;
  - `lint-imports` is green (`search` reaches `catalog` only through `catalog.application`);
  - the gate passes.

## T08 · Search infrastructure: diacritics folding and `QdrantKeywordIndex`
- **Type**: TDD (red: the unit folding test and the integration tests against the real qdrant, with stub adapters)
- **RFs**: RF5, RF6, RF7, RF9, RF10
- **Depends on**: T07, T04 (the integration `conftest.py`)
- **Files**:
  - `src/movie_search/search/infrastructure/text_folding.py`, with no fastembed import;
  - `src/movie_search/search/infrastructure/qdrant_keyword_index.py`;
  - `tests/unit/search/test_text_folding.py`;
  - `tests/integration/search/conftest.py`: the test alias `movies_keyword_test_<random>`, dropped with its collections after the session;
  - `tests/integration/search/test_qdrant_keyword_index.py`.
- **Tests to write first**:
  - **Unit**: `test_rf6_fold_diacritics` (`Amélie` → `Amelie`, `Almodóvar` → `Almodovar`, `ø` kept).
  - **Integration (`@pytest.mark.integration`), over the sample**:
    - **Rebuild and alias**:
      - `test_rf5_rebuild_on_fresh_qdrant_creates_alias`;
      - `test_rf5_rebuild_twice_one_collection_200_points`;
      - `test_rf5_other_alias_with_same_prefix_survives`;
      - `test_rf5_failure_before_swap_keeps_old_alias_and_deletes_partial`.
    - **Search**:
      - `test_rf7_blade_runner_first`;
      - `test_rf7_denis_villeneuve_tt1856101_in_top3`;
      - `test_rf7_coco_tt2380307_in_top3`;
      - `test_rf6_amelie_without_accent_finds_synthetic_amelie`.
    - **Empty results and errors**:
      - `test_rf9_stopwords_only_query_returns_empty`;
      - `test_rf9_missing_alias_returns_empty`;
      - `test_rf10_unreachable_qdrant_raises_search_unavailable` (`http://qdrant:1`).
- **Done when**: the unit and integration tests are green, and `uv run pytest -m integration tests/integration/search` and the gate pass.

## T09 · Search entrypoints: `/search` router and `index` command
- **Type**: Mechanical
- **RFs**: RF5, RF7, RF8, RF9, RF10
- **Depends on**: T07
- **Files**:
  - `src/movie_search/search/entrypoints/http.py`: `build_router(search_movies)`, `SearchResponse`, `SearchHit`;
  - `src/movie_search/search/entrypoints/cli.py`: `register(subparsers, index_movies_factory)`;
  - `tests/unit/search/test_http.py`, `tests/unit/search/test_index_cli.py`.
- **Tests to write first** (`TestClient` or argparse, with `create_autospec` of the use cases):
  - **Response**:
    - `test_rf7_response_shape`;
    - `test_rf7_missing_values_null_genres_empty`;
    - `test_rf7_q_trimmed_and_echoed`.
  - **Validation**:
    - `test_rf8_q_missing_422`;
    - `test_rf8_q_blank_422`;
    - `test_rf8_q_501_chars_422`;
    - `test_rf8_limit_out_of_range_or_not_int_422` (parametrized `0`, `51`, `abc`).
  - **Empty results and errors**:
    - `test_rf9_empty_results_200`;
    - `test_rf10_search_unavailable_503_generic_body`.
  - **`index` command**:
    - `test_rf5_index_prints_indexed_count`;
    - `test_rf5_index_empty_catalog_prints_0_exit_0`;
    - `test_rf5_index_failure_exit_1`.
- **Done when**: every case above is green and the gate passes.

## T10 · End-to-end wiring: bootstrap, `main.py`, `cli.py`
- **Type**: Mechanical
- **RFs / RNFs**: RF1, RF5, RF7, RNF1
- **Depends on**: T05, T08, T09
- **Files**:
  - `src/movie_search/bootstrap.py`:
    - cached builders for the Qdrant client and the BM25 model;
    - `build_index_movies()`, which calls `ensure_schema`;
    - `build_search_movies()`.
  - `src/movie_search/main.py`: `app`, with the router mounted.
  - `src/movie_search/cli.py`: registers `index`.
  - `tests/integration/test_bootstrap.py`, `tests/integration/test_e2e_search.py`.
- **Tests to write first**:
  - `test_rnf1_bm25_model_shared_instance` (`@pytest.mark.integration`): `build_index_movies()` and `build_search_movies()` receive the same BM25 model instance (`is`);
  - `test_e2e_ingest_index_search_blade_runner_top3` (`@pytest.mark.integration`): ingest the sample → index → `GET /search?q=Blade Runner` through `TestClient` → tt0083658 in the top 3.
- **Done when**:
  - `uv run python -m movie_search.cli index` after ingesting the sample prints `Indexed: 200`;
  - `uv run pytest -m integration` and the gate pass.

## T11 · Manual validation on the full dataset (human)
- **Type**: Manual
- **RFs**: all (DoD 1–6)
- **Depends on**: T10
- **Steps and checks**: run in the devcontainer, starting from an empty catalog and no keyword collection.

  1. **First ingest (DoD 1)**: `uv run python -m movie_search.cli ingest` (uses `MOVIES_DATA_PATH`).
     - Check: `Read: 47,203`, `Inserted: 46,963`, `Updated: 0`.
     - Check skips: `invalid_response 28`, `not_a_movie 3`, `missing_plot 209`.
  2. **Second ingest (DoD 2)**: `uv run python -m movie_search.cli ingest`.
     - Check: `Inserted: 0`, `Updated: 46,963`.
     - Count the catalog: `uv run python -c "import psycopg; print(psycopg.connect('postgresql://app:app@postgres:5432/movies').execute('select count(*) from catalog.movies').fetchone()[0])"` → `46963`.
  3. **Measure `BM25_AVG_LEN`** as in `design.md` § *Measuring `BM25_AVG_LEN`*.
     - Use a throwaway script that is not committed: `keyword_text`, then `fold_diacritics`, then fastembed's analyzer (`len(bm25._stem(SimpleTokenizer.tokenize(remove_non_alphanumeric(...))))`), averaged over the whole catalog.
     - Put the value in the `Settings` default.
  4. **Index twice (DoD 3)**: `uv run python -m movie_search.cli index`, run twice.
     - Check: both runs print `Indexed: 46,963`.
     - Find the collection: `curl -s http://qdrant:6333/aliases` → `movies_keyword` points to a single `movies_keyword__<20 digits>`.
     - Count its points: `curl -s http://qdrant:6333/collections/<that name>` → `points_count: 46963`.
     - Check for leftovers: `curl -s http://qdrant:6333/collections` → no other `movies_keyword__…` collection.
  5. **Anchor queries (DoD 4)**: start the API with `uv run uvicorn movie_search.main:app --host 0.0.0.0`. In the same container, `localhost` is the app itself.
     - `curl -s "http://localhost:8000/search?q=Blade%20Runner&limit=3"` → tt0083658 in the results.
     - `curl -s "http://localhost:8000/search?q=Denis%20Villeneuve&limit=3"` → at least one `imdb_id` from `select imdb_id from catalog.movies where 'Denis Villeneuve' = any(directors)`.
     - `curl -s "http://localhost:8000/search?q=Coco&limit=3"` → tt2380307.
     - `curl -s "http://localhost:8000/search?q=Amelie&limit=3"` → tt0211915.
     - Optional: add `-w '%{time_total}\n'` to each call to note the latency, for reference only.
  6. **Full gate (DoD 5)**: `uv run pytest && uv run lint-imports && uv run ruff check . && uv run ruff format --check .`
  7. **Write `specs/001-catalog-keyword-search/validation.md` (DoD 6)**:
     - for each RF1–RF10: the covering tests, the result and a verdict;
     - the outputs of steps 1–5;
     - the measured `BM25_AVG_LEN`;
     - the optional latencies;
     - a line confirming that `docs/architecture.md` is still true (constitution §6).
- **Done when**: every check in steps 1–6 holds and `validation.md` is written and approved.

---

## Coverage

| Req | Tasks | Tests |
|---|---|---|
| RF1 | T03, T04, T05, T10 | `test_rf1_blank_lines_…`, `test_rf1_limit_*`, `test_rf1_source_unavailable_writes_nothing`, `test_rf1_catalog_failure_on_batch_1_…`, `test_rf1_catalog_failure_on_batch_2_…`, `test_rf1_source_*` (integration), `test_rf1_ingest_*`, `test_e2e_…` |
| RF2 | T02, T03, T04, T05 | `test_rf2_invalid_record_*`, `test_rf2_missing_*`, `test_rf2_invalid_response`, `test_rf2_not_a_movie`, `test_rf2_precedence`, `test_rf2_uses_top_level_imdb_id_…`, `test_rf2_report_counts_per_reason`, `test_rf2_warning_logged_per_skip`, `test_rf2_source_invalid_utf8_…`, `test_rf2_ingest_report_format` |
| RF3 | T02, T04 | `test_rf3_*` (parsers, full sample record), `test_rf3_arrays_and_nulls_round_trip` |
| RF4 | T03, T04 | `test_rf4_last_record_wins_within_file`, `test_rf4_reimport_counts_updated`, `test_rf4_first_upsert_inserted_second_updated`, `test_rf4_repeated_id_in_batch_last_wins` |
| RF5 | T07, T08, T09, T10 | `test_rf5_rebuild_*`, `test_rf5_empty_catalog_indexes_0`, `test_rf5_other_alias_…`, `test_rf5_failure_before_swap_…`, `test_rf5_index_*`, `test_e2e_…` |
| RF6 | T06, T07, T08 | `test_rf6_title_written_twice`, `test_rf6_parts_in_order_…`, `test_rf6_missing_parts_left_out`, `test_rf6_documents_use_keyword_text`, `test_rf6_fold_diacritics`, `test_rf6_amelie_…` |
| RF7 | T04, T06, T07, T08, T09, T10 | `test_rf7_query_trimmed`, `test_rf7_default_limit_10`, `test_rf7_rank_*`, `test_rf7_equal_scores_…`, `test_rf7_results_*`, `test_rf7_hit_missing_from_catalog_…`, `test_rf7_get_many_*`, `test_rf7_blade_runner_first`, `test_rf7_denis_villeneuve_…`, `test_rf7_coco_…`, `test_rf7_response_shape`, `test_rf7_missing_values_…`, `test_rf7_q_trimmed_and_echoed`, `test_e2e_…` |
| RF8 | T06, T09 | `test_rf8_empty_or_blank_query_rejected`, `test_rf8_query_500_ok_501_rejected`, `test_rf8_limit_bounds`, `test_rf8_q_*_422`, `test_rf8_limit_out_of_range_or_not_int_422` |
| RF9 | T07, T08, T09 | `test_rf9_empty_index_returns_empty`, `test_rf9_stopwords_only_…`, `test_rf9_missing_alias_…`, `test_rf9_empty_results_200` |
| RF10 | T04, T07, T08, T09 | `test_rf10_unreachable_database_…`, `test_rf10_index_unavailable_propagates`, `test_rf10_catalog_unavailable_becomes_…`, `test_rf10_unreachable_qdrant_…`, `test_rf10_search_unavailable_503_…` |
| RNF1 | T08, T10 | `test_rnf1_bm25_model_shared_instance` (integration; the adapter receives an injected model in T08) |
| RNF2 | T01, T05, every task | the gate (`pytest -m "not integration"`); `lint-imports` (framework-free inner layers); `test_rnf2_importing_bootstrap_loads_no_driver`; no unit test imports fastembed, psycopg, qdrant-client or `movie_search.main` |

## Review notes (resolved 2026-11-03)

| # | Resolution |
|---|---|
| G1, G2, G3 | `docs/architecture.md` no longer lists types, use cases or code examples (constitution 1.3, architecture decisions 14–15); `design.md` is the reference for them. |
| G4 | Deferred imports in `bootstrap` (unit test in T05); the RNF1 test is an integration test (T10). |
| G5 | No unit test imports `movie_search.main` (`design.md` § *Composition root* and § *Test strategy*). |
| G6 | `.env.example` comments rewritten during the requirements clarification; T01 translates the remaining one. |
| G7 | `CatalogUnavailable` from `upsert_many` always becomes `ImportInterrupted` (also on the first batch); from `ensure_schema`, one-line error and exit 1 with no report (`design.md` § *CLI*). |
| G8 | DoD 4 checks Denis Villeneuve against the catalog's `directors`. |
| G9 | DoD 5 includes `ruff format --check`. |
| G10 | RF2 reports non-blank lines read. |
| G11 | `design.md` § *Dependencies*: approval by the human before T01. |
