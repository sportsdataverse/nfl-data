def test_skeleton_imports():
    """SP0 placeholder — proves the project + pytest config resolve. Replaced by real tests in SP1."""
    import polars as pl

    assert pl.DataFrame({"x": [1]}).height == 1
