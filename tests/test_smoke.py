def test_package_imports() -> None:
    import movie_search

    assert movie_search.__name__ == "movie_search"
