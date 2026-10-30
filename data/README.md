# Sample dataset: `omdb_sample.jsonl`

`omdb_sample.jsonl` is a small, versioned subset of the movie catalog used by
this project. It has **200 movies** and is meant for tests, quickstarts and
local experiments, so nobody has to rebuild the full dataset first.

The full dataset is **not** in the repository (see
[Why the full dataset is not published](#why-the-full-dataset-is-not-published)).

## Format

JSON Lines: one JSON object per line, sorted by `imdbID`. Each record wraps the
raw OMDb API response:

```json
{
  "imdb_id": "tt0032145",
  "raw": {
    "Title": "Wuthering Heights",
    "Year": "1939",
    "Genre": "Drama, Romance",
    "Director": "William Wyler",
    "Actors": "Merle Oberon, Laurence Olivier, David Niven",
    "Plot": "The story of unfortunate lovers Cathy and Heathcliff ...",
    "Ratings": [{"Source": "Internet Movie Database", "Value": "7.5/10"}, "..."],
    "imdbRating": "7.5",
    "imdbVotes": "20,678",
    "imdbID": "tt0032145",
    "Type": "movie",
    "Response": "True",
    "..."
  }
}
```

Notes:

- `raw` holds the OMDb fields as returned by the API (`Title`, `Year`, `Rated`,
  `Released`, `Runtime`, `Genre`, `Director`, `Writer`, `Actors`, `Plot`,
  `Language`, `Country`, `Awards`, `Poster`, `Ratings`, `Metascore`,
  `imdbRating`, `imdbVotes`, `imdbID`, `Type`, `DVD`, `BoxOffice`,
  `Production`, `Website`, `Response`).
- Almost every value is a string, including numbers (`"1939"`, `"20,678"`).
  Missing values appear as `"N/A"`.
- The sample was written with the schema of the full file, so a few keys that
  only apply to series or failed lookups (`Season`, `Episode`, `seriesID`,
  `totalSeasons`, `Error`) are present and always `null`.
- `Plot` is the **full** plot (`plot=full` in the API request), not the short
  one.

## How it was built

The data comes from two sources: **IMDb** (open datasets, used to choose the
movies) and **OMDb** (an API, used to get each movie's metadata and plot).

```
IMDb datasets ──► filter + join ──► movie_ids.txt ──► OMDb API ──► omdb_raw.jsonl ──► sample ──► omdb_sample.jsonl
 (title.basics,     (movies,          (49,392 IDs)      (async       (47,203 records)    (200 movies)
  title.ratings)     ≥ 1,000 votes)                      download)
```

### Step 1: Choose the movies with IMDb data

Notebook: [`notebooks/data-collection.ipynb`](../notebooks/data-collection.ipynb)

1. Download two files from the
   [IMDb non-commercial datasets](https://developer.imdb.com/non-commercial-datasets/):
   - `title.basics.tsv.gz`: type, title, year and genres of every IMDb title
     (about 12.9M rows).
   - `title.ratings.tsv.gz`: average rating and number of votes (about 1.7M
     rows).
2. Read both with Polars (`\N` read as null).
3. Keep only `titleType == "movie"`, join with the ratings on `tconst`, and
   keep movies with **at least 1,000 votes**. The result has **49,392 movies**
   (`imdb_movie_id`, `title`, `year`, `genres`, `imdb_rating`, `imdb_votes`)
   and is saved as `data/movies.parquet`.
4. Write the IMDb IDs, one per line, to `data/movie_ids.txt`.

### Step 2: Get each movie's metadata from OMDb

Notebook: [`notebooks/data-collection.ipynb`](../notebooks/data-collection.ipynb)

For each ID in `movie_ids.txt`, the notebook calls the
[OMDb API](https://www.omdbapi.com/) (`?i=<imdb_id>&plot=full`). The API key
is read from the `OMDB_API_KEY` variable in `.env`.

The downloader is an async pipeline (`aiohttp` + `asyncio`):

- **Concurrency:** a queue of IDs consumed by 5 workers.
- **Retries:** up to 5 attempts per ID, with growing waits for HTTP 429 (rate
  limit), 5xx errors and timeouts (40 s per request).
- **Output:** each response is added as one line to `data/omdb_raw.jsonl` as
  `{"imdb_id": ..., "raw": <OMDb JSON>}`. A lock keeps writes from overlapping.
- **Checkpoint:** each finished ID is added to `data/processed_ids.txt`, so a
  run that stops can continue without fetching the same IDs again.

Logical OMDb errors (`"Response": "False"`) are saved as well. The final
`omdb_raw.jsonl` has **47,203 records**: 47,175 valid and 28 with
`Incorrect IMDb ID.`.

### Step 3: Take the sample

Notebook: [`notebooks/make-sample.ipynb`](../notebooks/make-sample.ipynb)

1. **Keep valid records:** `Response == "True"` and a non-empty `Plot` (not
   `""` and not `"N/A"`).
2. **Add 21 fixed "anchor" movies.** They are always in the sample because the
   test queries depend on them, including titles that share a name:

   | Theme                  | Movies                                                         |
   | ---------------------- | -------------------------------------------------------------- |
   | Dogs                   | Hachi: A Dog's Tale (2009), Marley & Me, Hachiko (1987)        |
   | Star Wars              | Episode IV, Episode V, The Force Awakens                       |
   | Blade Runner           | Blade Runner, Blade Runner 2049                                |
   | Popular / sci-fi       | Inception, Interstellar, The Matrix, Toy Story                 |
   | Same title, two movies | Coco (2017 / 2009), Parasite (2019 / 1982), Titanic (1997 / 1953) |
   | Other                  | Spirited Away, Amores Perros, The Godfather                    |

3. **Fill the other 179 places at random** from well-known movies (`imdbVotes`
   ≥ **20,000**), leaving out the anchors. The random seed is fixed
   (`random.seed(42)`), so running the notebook again on the same
   `omdb_raw.jsonl` gives the same sample.
4. Sort by `imdbID` and write `data/sample/omdb_sample.jsonl` with
   `write_ndjson`.

Result: 200 movies, released from 1939 to 2025.

### Rebuild it

1. Get a free OMDb API key at <https://www.omdbapi.com/apikey.aspx> and put it
   in `.env`:

   ```
   OMDB_API_KEY=your_key
   ```

2. Run `notebooks/data-collection.ipynb` to download the IMDb files and build
   `data/omdb_raw.jsonl`. With a free key (1,000 requests per day), the full
   download takes many days. The checkpoint lets each run continue where the
   last one stopped.
3. Run `notebooks/make-sample.ipynb`.

## Why the full dataset is not published

Only this sample is in git. `.gitignore` leaves out everything else in
`data/`: the IMDb files, `movies.parquet`, `movie_ids.txt`,
`omdb_raw.jsonl` and `processed_ids.txt`. The reasons:

- **Licensing and terms of use.** The IMDb datasets are for personal and
  non-commercial use under
  [IMDb's terms](https://developer.imdb.com/non-commercial-datasets/), and do
  not allow sharing them again as a dataset. OMDb content is published under a
  non-commercial license (CC BY-NC 4.0) and is meant to be used through the
  API with your own key. Posting a full copy of either in a public repository
  would mean distributing their data in bulk, beyond what those terms allow.
  A small sample for tests and demos is a much smaller use of that data.
- **Size.** The raw IMDb files are about 240 MB and `omdb_raw.jsonl` is about
  59 MB. Files that large make the repository heavy, and git does not handle
  them well.
- **It can be rebuilt.** The notebooks have every step, so anyone with an OMDb
  key can create the dataset again from the original sources. There is no
  need to keep a copy in git.
- **Freshness.** Ratings, vote counts and plots change over time. Downloading
  them again gives current data; a committed copy would get old.

> The sample is provided only for development and testing. IMDb and OMDb
> keep all rights to their data.
