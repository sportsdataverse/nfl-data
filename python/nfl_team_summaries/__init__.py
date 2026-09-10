"""Season team + player summaries for the NFL ("Binion box score" grid).

The NFL twin of ``cfbfastR-cfb-data``'s ``team_summaries`` producer. It reads
the released ``nfl_model_pbp`` season parquet (nfl.com Shield JSON ->
nflfastR-parity -> sdv-py EP/WP enrichment) and emits five tables under the
SAME column contract the college tables carry, so gameonpaper.com's shared
components render either league:

``team_summaries``  one row per team: the ``{metric}_{off|def|margin}[_{pass|rush}][_rank]``
                    grid, drive efficiency, opponent-adjusted EPA, plus the
                    rbsdm.com extras (pass rate over expected, neutral pass
                    rate, fourth-down decisions, luck).
``passing`` / ``rushing`` / ``receiving``  player leaderboards among qualifiers.
``percentiles``     1..99 quantiles of per-game team metrics (the distribution
                    reference behind the site's trends chart).

Team key is the ESPN team id (``team_id``) because that is the id every site
URL, logo and API filter uses; ``pos_team`` carries the nflverse abbreviation.
"""
