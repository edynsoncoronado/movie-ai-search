# 001 · Catalog ingestion and keyword search (BM25)

**Status:** clarified · **Constitution:** 1.3 · **Modules:** `catalog`, `search`

## Goal

Load the OMDb dump into the catalog, build a BM25 keyword index from it and expose `GET /search`. The goal is that every layer (domain, application, infrastructure, entrypoints) of `catalog` and `search` works end to end before semantic search is added in spec 002.

## Depends on
Constitution 1.3 · `docs/architecture.md` key decisions 10–12 (BM25 on Qdrant sparse vectors, PostgreSQL catalog as source of truth, full rebuild with atomic alias swap).

## User stories

- **US1.** As an operator, I want to load the OMDb dump into the catalog, so that movies are stored clean and typed.
- **US2.** As an operator, I want to build the keyword index from the catalog, so that movies can be searched.
- **US3.** As a client, I want to search movies by words in their title, people, genres or plot, so that I get the most relevant movies first.

## Functional requirements
### Ingestion (US1)

**RF1 · Ingest from a JSONL file**
- WHEN the operator runs `ingest [PATH]`, THE SYSTEM SHALL read every line of the OMDb JSONL file at `PATH` (or at `MOVIES_DATA_PATH` if `PATH` is not given) and store the valid movies in the catalog.
- WHERE `--limit N` is given, THE SYSTEM SHALL stop after storing N movies, counting both inserted and updated movies. Skipped records do not count toward N.
- IF no path is given and `MOVIES_DATA_PATH` is not set, or the file does not exist or cannot be read, THEN THE SYSTEM SHALL exit with a non-zero code and a clear message, without writing any movie.
- IF `N` is not an integer ≥ 1, THEN THE SYSTEM SHALL exit with a usage error without reading the file.
- THE SYSTEM SHALL ignore blank lines: they are not reported as skipped.
- IF ingestion fails after it has started writing (e.g. the catalog becomes unreachable), THEN THE SYSTEM SHALL keep the movies already stored, report the counts so far and exit with a non-zero code. Running `ingest` again is safe (RF4).

**RF2 · Record validation**
- THE SYSTEM SHALL trim every string value before validating or normalizing it.
- IF a record cannot be stored, THEN THE SYSTEM SHALL skip it with the first matching reason, in this order:
  1. `invalid_record`: the line is not valid JSON, or not an object with an object `raw`;
  2. `missing_imdb_id`: the top-level `imdb_id` is missing, `null`, empty, or does not match `tt` followed by 7 or more digits;
  3. `invalid_response`: `Response` is `"False"`;
  4. `not_a_movie`: `Type` is not `"movie"`;
  5. `missing_title`: `Title` is missing, empty or `"N/A"`;
  6. `missing_plot`: `Plot` is missing, empty or `"N/A"`.
- THE SYSTEM SHALL use the top-level `imdb_id` as the movie identity and ignore `raw.imdbID`.
- WHEN a record is skipped, THE SYSTEM SHALL log a warning with the line number, the `imdb_id` (if any) and the reason, and continue with the next line.
- WHEN ingestion finishes, THE SYSTEM SHALL report how many non-blank lines were read, how many movies were inserted and updated, and how many records were skipped per reason.

**RF3 · Field normalization**
- THE SYSTEM SHALL treat `"N/A"` and empty strings as missing: `None` for scalar fields, an empty list for list fields.
- IF `Year` starts with four digits, THEN THE SYSTEM SHALL store those digits as an integer (`"2025–"` → `2025`, `"1994"` → `1994`); otherwise it SHALL store the year as missing.
- THE SYSTEM SHALL store `Runtime` as minutes (`"104 min"` → `104`), `imdbVotes` as an integer (`"20,678"` → `20678`) and `imdbRating` as a float (`"7.8"` → `7.8`).
- IF a numeric field does not match its expected format, THEN THE SYSTEM SHALL store it as missing instead of skipping the record or failing the ingestion.
- THE SYSTEM SHALL split `Genre`, `Director`, `Writer`, `Actors`, `Language` and `Country` on commas, trim each value and drop empty values.
- THE SYSTEM SHALL drop the value `"None"` from `Language` (`"None"` → `[]`; `"None, English"` → `["English"]`).

**RF4 · Idempotent ingestion**
- WHEN a movie whose `imdb_id` already exists in the catalog, or earlier in the same file, is ingested, THE SYSTEM SHALL update it instead of creating a duplicate (the last record wins) and count it as updated.

### Indexing (US2)

**RF5 · Full rebuild with atomic swap**
- WHEN the operator runs `index`, THE SYSTEM SHALL build a new keyword index from all the movies in the catalog and then make `/search` use it in one atomic step, replacing the previous index.
- WHILE `index` is running, THE SYSTEM SHALL keep serving `/search` from the previous index.
- WHEN the swap succeeds, THE SYSTEM SHALL delete the previous keyword collection.
- IF `index` fails before the swap, THEN THE SYSTEM SHALL leave the previous index unchanged and exit with a non-zero code.
- IF `index` fails before the swap, THEN THE SYSTEM SHALL also try to delete the partially built collection; a failure to delete it is logged and does not change the exit code.
- WHEN `index` finishes, THE SYSTEM SHALL report how many movies were indexed. IF the catalog is empty, THEN THE SYSTEM SHALL build an empty index and exit successfully.

**RF6 · Keyword text**
- THE SYSTEM SHALL build each movie's keyword text from its title (written twice, as a title boost), directors, actors, genres and plot, omitting missing values.
- THE SYSTEM SHALL tokenize the keyword text and the queries with the same BM25 analyzer: diacritics folding (`é` → `e`), lowercasing, English stopword removal and English stemming.

### Search (US3)

**RF7 · Keyword search**
- WHEN a client sends `GET /search?q=<text>&limit=<n>`, THE SYSTEM SHALL search with `q` trimmed and return `{"query": <trimmed q>, "results": [...]}`.
- `results` holds up to `n` movies, ordered by descending BM25 score, with ties broken by `imdb_id` ascending.
- THE SYSTEM SHALL return for each movie: `imdb_id`, `title`, `year`, `genres`, `imdb_rating`, `poster_url`, `plot` and `score`.
  - Missing values are `null`; missing genres are `[]`.
  - `score` is the raw BM25 score: it is not bounded and is not comparable across queries.
- WHEN `limit` is not given, THE SYSTEM SHALL use 10.
- IF a movie returned by the keyword index is not in the catalog, THEN THE SYSTEM SHALL leave it out of `results` and log a warning; `results` may then hold fewer than `n` movies.

**RF8 · Input validation**
- IF `q` is missing, or is empty after trimming, THEN THE SYSTEM SHALL respond `422`.
- IF `q` is longer than 500 characters after trimming, THEN THE SYSTEM SHALL respond `422`.
- IF `limit` is not an integer between 1 and 50, THEN THE SYSTEM SHALL respond `422`.
- Validation errors use FastAPI's standard error body.

**RF9 · No results**
- IF no movie matches the query, THEN THE SYSTEM SHALL respond `200` with `results: []`. This covers queries that produce no tokens (only stopwords or punctuation), and the case where the keyword index has not been built yet or is empty.

**RF10 · Search backends unavailable**
- IF the keyword index or the catalog cannot be reached, THEN THE SYSTEM SHALL respond `503` without exposing internal details.

## Non-functional requirements

- **RNF1** The BM25 model is loaded once per process (API and `index` command), never per request or per batch.
- **RNF2** Unit tests do not load fastembed and use no PostgreSQL, Qdrant or network: they use in-memory fakes of the ports (including `KeywordIndex`). fastembed, PostgreSQL and Qdrant run only in tests marked `integration`.
- No latency target in 001: latency is first measured in spec 004.

## Field usage

| Field | Stored (catalog) | BM25 text (001) | Dense text (002) | Filters (003) | `/search` response |
|---|---|---|---|---|---|
| `imdb_id` | ✅ primary key | | | | ✅ |
| `title` | ✅ | ✅ ×2 | ✅ | | ✅ |
| `year` | ✅ (nullable) | | ✅ | ✅ | ✅ |
| `genres` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `directors`, `actors` | ✅ | ✅ | | | |
| `plot` | ✅ | ✅ | ✅ | | ✅ |
| `writers`, `languages`, `countries` | ✅ | | | to decide in 003 | |
| `runtime_min`, `imdb_votes` | ✅ | | | ✅ | |
| `imdb_rating` | ✅ | | | ✅ | ✅ |
| `rated`, `awards`, `poster_url` | ✅ | | | | `poster_url` |

Not stored: `Released` (`year` covers the filters), `Metascore`, `BoxOffice`, `DVD`, `Production`, `Website`, `Ratings`.

## Data facts (profiling, 2026-11-02 and 2026-11-03)

Source: `omdb_raw.jsonl`, 47,203 records.
- **Skips with the RF2 rules**: 28 `invalid_response`, 3 `not_a_movie` (2 episodes, 1 series) and 209 `missing_plot`, leaving 46,963 movies stored.
  - The 3 non-movies are counted only as `not_a_movie`, although 2 of them (the series and one episode) also lack a plot.
  - There are no invalid lines, no blank lines and no records without a title.
- **Identity**: every `imdb_id` matches `raw.imdbID` and the pattern `tt` + 7–8 digits; no duplicate `imdbID`.
- **Formats**:
  - apart from `"N/A"`, `Runtime` and `imdbVotes` show no unexpected formats;
  - `Year` has one unexpected value (`"2025–"`, the series, which is skipped);
  - every stored movie has a 4-digit year;
  - no title has leading or trailing spaces.
- **Missing values**: `Rated` 13,090 · `imdbRating` 859 · `Released` 609 · `imdbVotes` 379 · `Language` 309 · `Genre` 146 · `Actors` 118 · `Poster` 83 · `Director` 37.
- **`"None"` in `Language`**: 206 records, 76 with exactly `"None"` and 130 mixed (e.g. `"None, English"`).
- **Diacritics**: 8,467 stored movies have non-ASCII characters in the title, directors or actors (e.g. *Amélie*, Almodóvar).
- **Annotations in names**: 1 director and 1 actor carry a parenthetical note (e.g. `"Reto Caduff(co-director)"`); kept as is.
- **Plot length in words**: P50 65 · P90 149 · P95 195 · max 1,199.
- **Duplicate titles**: 2,635 titles are shared by more than one movie (e.g. *Coco* 2009 and 2017).
- **Sample** (`data/sample/omdb_sample.jsonl`, 200 movies): no record triggers a skip reason, so the RF2 tests need their own fixtures under `tests/`.

## Out of scope

- 002: semantic search and dense vectors; hybrid fusion with RRF.
- 003: filters extracted by an LLM, and `/ask`.
- 004: evaluation metrics and latency.
- Also out: pagination, authentication, downloading data from the OMDb API, UI, deleting movies, concurrent runs of `ingest` and `index` (single operator).

## Definition of done

1. `ingest` on the full dataset reports:
   - 47,203 lines read, 46,963 inserted, 0 updated;
   - skips: 28 `invalid_response`, 3 `not_a_movie`, 209 `missing_plot`.
2. Running `ingest` a second time reports 0 inserted and 46,963 updated, and the catalog still has 46,963 movies.
3. Running `index` twice leaves:
   - exactly 46,963 points in the collection that `/search` uses;
   - no other keyword collection from earlier runs.
4. `GET /search` returns the expected movie in the top 3 for:
   - `"Blade Runner"` → tt0083658
   - `"Denis Villeneuve"` → any movie whose `directors` include Denis Villeneuve (checked against the catalog, since `/search` does not return directors)
   - `"Coco"` → tt2380307
   - `"Amelie"` (without the accent) → tt0211915
5. Every RF is covered by at least one test that names it, and the full gate passes: `pytest`, `lint-imports`, `ruff check` and `ruff format --check`.
6. `validation.md` records each RF, its test and the result, and confirms that `docs/architecture.md` is still true (constitution §6). Optionally, it also records the observed latency of the queries in point 4, as a reference only (no threshold).
