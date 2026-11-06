CREATE SCHEMA IF NOT EXISTS catalog;

CREATE TABLE IF NOT EXISTS catalog.movies (
    imdb_id      text PRIMARY KEY,
    title        text        NOT NULL,
    year         smallint,
    plot         text        NOT NULL,
    genres       text[]      NOT NULL DEFAULT '{}',
    directors    text[]      NOT NULL DEFAULT '{}',
    writers      text[]      NOT NULL DEFAULT '{}',
    actors       text[]      NOT NULL DEFAULT '{}',
    languages    text[]      NOT NULL DEFAULT '{}',
    countries    text[]      NOT NULL DEFAULT '{}',
    runtime_min  integer,
    imdb_votes   integer,
    imdb_rating  real,
    rated        text,
    awards       text,
    poster_url   text,
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now()
);
