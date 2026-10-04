"""Upload NFL model artifacts (.ubj + model-card .json) to a GitHub release.

Card sidecar naming (from model_training.play_level.model_card):
    ``write_model_card`` writes ``Path(model_path).with_suffix(".json")``,
    so a model file ``ep.ubj`` has its card at ``ep.json`` (same stem).
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from sportsdataverse.release import upload_release_sidecars

GH_TIMEOUT_SECONDS = 300

# Release-notes body used when auto-creating a missing release.
#: Release sidecar metadata: the loader a consumer reads each tag through.
#: R's sportsdataverse_save() writes this as package_function.txt/.json beside
#: every published asset; the Python publisher dropped it along with the
#: timestamp pair, so the nfl_* tags have never carried either. The model-artifact
#: tags have no reader -- they are consumed by sdv-py at model-load time, not by a
#: loader -- so they name their producer, the convention the ncaa_*_rapm tags
#: already carry on their published sidecars. A tag that is not listed still gets
#: its timestamp re-stamped; it just ships no package_function.
PKG_FUNCTION: dict[str, str] = {
    "nfl_4th_down_models": "python/nfl_model_publish/decision_models_artifacts.py",
    "nfl_defense_vs_position": "python/nfl_data_08_defense_vs_position.py",
    "nfl_espn_qbr": "sportsdataverse.nfl.load_nfl_espn_qbr()",
    "nfl_metric_curves": "python/nfl_data_07_metric_curves.py",
    "nfl_model_artifacts": "python/nfl_model_publish/artifacts.py",
    "nfl_model_pbp": 'sportsdataverse.nfl.load_nfl_pbp(source="sdv")',
    "nfl_paper_index_games": "python/nfl_data_09_paper_index_games.py",
    "nfl_player_stats": 'sportsdataverse.nfl.load_nfl_player_stats(source="sdv")',
    "nfl_players": 'sportsdataverse.nfl.load_nfl_players(source="sdv")',
    "nfl_ratings_weekly": "sportsdataverse.nfl.load_nfl_ratings_weekly()",
    "nfl_rosters": 'sportsdataverse.nfl.load_nfl_rosters(source="sdv")',
    "nfl_team_stats": 'sportsdataverse.nfl.load_nfl_team_stats(source="sdv")',
}


_RELEASE_BODY = {
    "nfl_model_artifacts": (
        "NFL model artifacts (EP/WP-spread/WP-naive/CP .ubj) + model cards."
    ),
    "nfl_model_pbp": (
        "NFL compiled play-by-play (EP/WP/QBR enriched; Python-built)."
    ),
    "nfl_rosters": (
        "SDV-native NFL season rosters (ESPN-sourced; Python-built)."
    ),
    "nfl_players": (
        "SDV-native NFL player index (ESPN athlete crosswalk; Python-built)."
    ),
    "nfl_player_stats": (
        "SDV-native NFL player stats (week-level, REG+POST; aggregated from "
        "SDV-native play-by-play; Python-built)."
    ),
    "nfl_espn_qbr": (
        "SDV-native ESPN Total QBR -- qualified-passer leaderboard (season + week; "
        "ESPN fitt/v3 isqualified=true; values byte-match nflverse espn_data's "
        "qualified rows). Python-built."
    ),
    "nfl_metric_curves": (
        "NFL rate curves along a continuous axis, one file per season: FG% by kick "
        "distance, completion% and EPA by air-yards bucket, 4th-down conversion by "
        "yards to go and success by down x distance, each bucket with attempts, "
        "successes, rate and EPA per attempt, for the league, every team and every "
        "credited kicker / passer (regular season + postseason). Built by stage 07 from "
        "nfl_model_pbp, so it spans the same seasons; a season whose pbp carries no "
        "air yards has no air-yards rows. Ids: team entity_id / team_id are the ESPN "
        "team id; player entity_id is the ESPN athlete id re-keyed from nflfastR via the "
        "players master, with gsis_id kept alongside -- a player with no ESPN match "
        "keeps entity_id = gsis_id and id_source = gsis."
    ),
    "nfl_defense_vs_position": (
        "What each NFL defense allowed to quarterbacks, running backs, wide receivers "
        "and tight ends, one file per season from 1999 (the first nfl_model_pbp season): "
        "one row per (season, team_id, position_group), regular season + postseason. "
        "EPA per play, success rate and explosive rate allowed, plus sack rate (QB), "
        "rushing yards per carry (RB) and receiving yards per target (WR, TE), each "
        "with a 0-100 percentile among the defenses with 3+ games in that position "
        "group, where higher is always the better defense. team_id is the ESPN team "
        "id; position groups come from the nflverse season roster on the gsis id. WR "
        "and TE rates are on targets naming a receiver: unattributed_target_share is "
        "the share of passes thrown against the defense that name none (about 4% in "
        "2024, throwaways; about 40% in 2003-2008, when the play-by-play names no "
        "receiver on any incompletion or interception, so those six seasons' WR and "
        "TE rows are completions only). Built by stage 08 with sdv-py "
        "defense_vs_position."
    ),
    # No fit years here on purpose: they live in sportsdataverse.paper_index, and
    # importing it in this module would stop every publish stage on an sdv-py older
    # than the port (cfbfastR-cfb-data hit exactly that, e3e4a4e8).
    "nfl_paper_index_games": (
        "Game on Paper's Paper Index for the NFL, one file per season from 2002 (the "
        "first espn_nfl_pbp season): one row per team per scored game with paper_share, "
        "the team's deserved-win probability from eight performance margins (success, "
        "explosive plays, explosiveness, scoring-opportunity conversion, points per "
        "opportunity, field position, havoc, turnovers), the opponent's share, the "
        "eight margins and whether the team won. A game is scored when it is completed, "
        "has a winner (a tie has no row) and both sides ran 20+ scrimmage snaps; the Pro "
        "Bowl is out. Preseason (season_type 1, from 2026), regular season (2) and "
        "postseason (3) are all in: filter season_type before summing. game_id and "
        "team_id are the ESPN ids. paper_index_span says where the season sits against "
        "the fit: train = that season's games were part of the fit, so its shares are "
        "in-sample; holdout = scored out of sample at fit time; out_of_span = never seen "
        "by the fit and never evaluated (the spans are sportsdataverse.paper_index's "
        "TRAIN_SEASONS and HOLDOUT_SEASONS). The regular-season sums are the "
        "deserved_wins / luck_wins / luck_z columns of nfl_team_summaries. Built by "
        "stage 09 with sdv-py paper_index_games from espn_nfl_pbp."
    ),
}


def plan_uploads(models_dir) -> list[Path]:
    """Discover model files + their card sidecars in *models_dir*.

    For each ``*.ubj`` found, pairs it with its sidecar card: a ``.json`` file
    sharing the same stem (e.g. ``ep.ubj`` + ``ep.json``).  The card is
    included only when it exists.

    Args:
        models_dir: Directory containing ``*.ubj`` model files (and optionally
            their ``.json`` card sidecars).

    Returns:
        De-duplicated list of :class:`pathlib.Path` objects in stable order
        (model first, then its card).
    """
    models_dir = Path(models_dir)
    seen: set[Path] = set()
    out: list[Path] = []

    for model_path in sorted(models_dir.glob("*.ubj")):
        if model_path not in seen:
            seen.add(model_path)
            out.append(model_path)
        # Card sidecar: same stem, .json extension
        card_path = model_path.with_suffix(".json")
        if card_path.exists() and card_path not in seen:
            seen.add(card_path)
            out.append(card_path)

    return out


def _gh_runner(args: list) -> None:
    subprocess.run(["gh", *args], check=True, timeout=GH_TIMEOUT_SECONDS)


def _gh_release_exists(tag: str, repo: str) -> bool:
    """Return True if a GitHub release for *tag* already exists on *repo*."""
    r = subprocess.run(
        ["gh", "release", "view", tag, "--repo", repo],
        capture_output=True,
        timeout=GH_TIMEOUT_SECONDS,
    )
    return r.returncode == 0


def upload_artifacts(
    models_dir,
    tag: str,
    repo: str,
    *,
    pattern: str | None = None,
    dry_run: bool = False,
    runner=None,
    exists_check=None,
) -> dict:
    """Upload each discovered artifact to the *tag* release on *repo*.

    By default (``pattern=None``) the uploaded set is each ``*.ubj`` model plus
    its ``.json`` card sidecar (:func:`plan_uploads`).  Pass *pattern* to upload
    a flat glob instead (e.g. ``"roster_*.parquet"`` or ``"players.parquet"``);
    no card-sidecar pairing is done in that mode.

    The release is created if it does not already exist (``gh release upload``
    does not create one), so a single call is self-sufficient.  *runner* and
    *exists_check* are injectable for hermetic testing.

    Args:
        models_dir: Directory containing the artifact files.
        tag: GitHub release tag (e.g. ``"nfl_model_artifacts"``).
        repo: GitHub repository slug (e.g. ``"sportsdataverse/sportsdataverse-data"``).
        pattern: Optional glob (relative to *models_dir*) selecting a flat set of
            files to upload. When ``None``, falls back to the ``*.ubj`` + card
            discovery in :func:`plan_uploads`.
        dry_run: When True, print what would be done without touching the network.
        runner: Callable ``(args: list) -> None`` that executes a ``gh`` sub-command
            (injectable for testing; defaults to :func:`_gh_runner`).
        exists_check: Callable ``(tag: str, repo: str) -> bool`` that checks whether
            the release already exists (injectable for testing; defaults to
            :func:`_gh_release_exists`).

    Returns:
        A dict with keys ``uploaded`` (int), ``files`` (list[str]),
        ``tag`` (str), and ``created_release`` (bool).
    """
    run = runner or _gh_runner
    exists = exists_check or _gh_release_exists
    if pattern is None:
        files = plan_uploads(models_dir)
    else:
        files = sorted(Path(models_dir).glob(pattern))
    created_release = False

    if dry_run:
        print(f"[dry-run] would ensure release {repo}:{tag} exists")
    elif not exists(tag, repo):
        body = _RELEASE_BODY.get(tag, f"{tag} (auto-created by nfl_model_publish).")
        run(["release", "create", tag, "--repo", repo, "--title", tag, "--notes", body])
        created_release = True

    uploaded = 0
    for f in files:
        if dry_run:
            print(f"[dry-run] would upload {f} -> {repo}:{tag}")
            continue
        run(["release", "upload", tag, str(f), "--repo", repo, "--clobber"])
        uploaded += 1

    # stamp LAST so the timestamp describes a finished upload, and only when
    # something actually uploaded -- a stamp on a no-op run would claim data
    # moved when it did not
    if uploaded:
        upload_release_sidecars(tag, runner=run, pkg_function=PKG_FUNCTION.get(tag), repo=repo)

    return {
        "uploaded": uploaded,
        "files": [str(f) for f in files],
        "tag": tag,
        "created_release": created_release,
    }
