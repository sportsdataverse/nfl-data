"""nfl_ratings_weekly — per-week as-of vintages of the NFL ratings spine.

Mirrors cfbfastR-cfb-data's ``cfb_ratings_weekly`` job with one deliberate
semantic upgrade: rows are keyed ``(season, as_of_week)`` with STRICTLY
EXCLUSIVE semantics — the vintage at ``as_of_week = W`` is fit on plays
from games with ``gameday`` strictly before week ``W``'s FIRST kickoff,
i.e. exactly what a forecaster held entering that week. (The CFB twin's
``through_week = W`` cutoff is week W's LAST kickoff date, an inclusive
labeling that has repeatedly invited leaks downstream; new datasets use
the exclusive convention.)

Publishes per-season parquet assets ``nfl_ratings_weekly_{season}.parquet``
to the ``nfl_ratings_weekly`` release on sportsdataverse/sportsdataverse-data.
"""
