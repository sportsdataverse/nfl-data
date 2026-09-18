"""Dataset registry for the ``espn_nfl_*`` processed-game family.

The NFL twin of ``cfbfastR-cfb-data``'s ``cfb_data_build.config``: one
:class:`DatasetSpec` per released dataset, built one of two ways from a
per-game *final* payload (the ``NFLPlayProcess`` output, see
:mod:`nfl_espn_build.process`):

* ``block`` set -- a generic flatten of a (possibly nested) list-of-dicts block
  (``flat_block_frame``): the ten ``advBoxScore`` sections and the per-play
  participants.
* ``reshaper`` set -- a bespoke per-game reshape registered in
  :mod:`nfl_espn_build.reshapers` (pbp, team/player box pivots, drives).

The cfb family gets its finals from ``cfbfastR-cfb-raw`` (the scraper runs the
processor); ``nfl-raw`` is scraping-only, so here the processor runs in this
repo over the committed ESPN summaries + play participants and caches the
final per game.
"""

from __future__ import annotations

import functools
import json
from dataclasses import dataclass
from importlib import metadata

#: Bumped when the final payload's shape or semantics change for reasons a
#: sdv-py release number does not capture (a new embedded block, a changed
#: key, a processor fix landed on git main). Cached finals whose
#: ``processing_version`` differs are reprocessed.
#: 2: NFLPlayProcess scoring_opp read the home-oriented start.yardLine
#:    instead of start.yardsToEndzone (sportsdataverse-py, 2026-09-15).
#: 3: play_participants rows carry {type}_position_id (sportsdataverse-py
#:    usage box, 2026-09-15) -- the position-group splits need them.
#: 4: the football-sources NFL game-state sweep (sportsdataverse-py #504 and
#:    #519, merged to main via #531). Replayed over 13 real nfl-raw summaries
#:    2002-2026: EP_start changes on 1,828/1,857 rows, EPA on 1,685,
#:    end.TimeSecsRem on 1,760 (N8 end clock), wp_before on 1,124 and
#:    wp_after on 1,700; the frame gains a ``roof`` column; the N5 dedupe fix
#:    recovers real plays the old filter dropped (163 -> 177 in one game).
#:    Every 0.1.4+8dbbfa2e.3 final must rebuild.
SCHEMA_REV = 4


@functools.lru_cache(maxsize=1)
def _sdv_git_sha() -> str:
    """Short commit of a git-installed sportsdataverse; ``""`` for a PyPI install.

    Both cron workflows install sdv-py from git ``main`` (the producer surface
    lands there before a release), so the version string alone cannot tell two
    library states apart -- ``0.1.4`` covers every commit between releases, and
    a lock bump alone would leave every final's stamp unchanged and reprocess
    would skip all of them. Same local-segment convention as
    ``cfbfastR-cfb-raw``'s ``PROCESSING_VERSION``.
    """
    try:
        raw = metadata.distribution("sportsdataverse").read_text("direct_url.json") or "{}"
        return str(json.loads(raw).get("vcs_info", {}).get("commit_id", ""))[:8]
    except Exception:  # noqa: BLE001 -- absent file / PyPI install / editable oddities
        return ""


def processing_version() -> str:
    """``<sdv-py version>+[<sdv-py git sha>.]<SCHEMA_REV>``.

    Stamped on every cached final, in every written parquet's file-level
    metadata, and in each dataset's manifest row, so a release tag always says
    which library state cut each season.
    """
    try:
        sdv = metadata.version("sportsdataverse")
    except metadata.PackageNotFoundError:  # pragma: no cover - editable oddities
        sdv = "unknown"
    return f"{sdv}+" + ".".join(p for p in (_sdv_git_sha(), str(SCHEMA_REV)) if p)


@dataclass(frozen=True)
class DatasetSpec:
    """How to build one released dataset from a final payload.

    Attributes:
        dataset: directory name under the output root and the registry key.
        stem: output file stem (``{stem}_{season}.parquet``).
        tag: the ``sportsdataverse-data`` release tag.
        block: nested key path to a list-of-dicts block for the generic
            flatten (e.g. ``("advBoxScore", "team")``); ``None`` for bespoke.
        reshaper: key into :data:`nfl_espn_build.reshapers.RESHAPERS`;
            ``None`` for generic-flatten datasets.
    """

    dataset: str
    stem: str
    tag: str
    block: tuple[str, ...] | None = None
    reshaper: str | None = None
    #: a ``sportsdataverse.football.usage_box`` section computed at BUILD time
    #: from the final's plays + participants (never read from the cache, so
    #: the installed sdv-py's definitions always win without a reprocess)
    usage_section: str | None = None
    #: sum the per-game usage rows into one season leaderboard
    aggregate: bool = False
    #: a ``sportsdataverse.football.tendencies`` cut over the season's plays:
    #: ``"team"`` (season x team), ``"coach"`` (season x team x head coach) or
    #: ``"careers"`` (every written coach season summed per coach, one file)
    tendencies: str | None = None


def _adv(section: str, key: str | None = None) -> DatasetSpec:
    key = key or section
    return DatasetSpec(
        f"adv_{key}", f"adv_{key}", f"espn_nfl_adv_{key}", block=("advBoxScore", section)
    )


REGISTRY: dict[str, DatasetSpec] = {
    # --- bespoke per-game reshapers -------------------------------------
    "pbp": DatasetSpec("pbp", "play_by_play", "espn_nfl_pbp", reshaper="pbp"),
    "team_box": DatasetSpec("team_box", "team_box", "espn_nfl_team_box", reshaper="team_box"),
    "player_box": DatasetSpec(
        "player_box", "player_box", "espn_nfl_player_box", reshaper="player_box"
    ),
    "drives": DatasetSpec("drives", "drives", "espn_nfl_drives", reshaper="drives"),
    # --- generic flatten (top-level block) ------------------------------
    "play_participants": DatasetSpec(
        "play_participants",
        "play_participants",
        "espn_nfl_play_participants",
        block=("play_participants",),
    ),
    # --- generic flatten (advBoxScore sections; same keys as the cfb family) --
    "adv_team": _adv("team"),
    "adv_passing": _adv("pass", "passing"),
    "adv_rushing": _adv("rush", "rushing"),
    "adv_receiving": _adv("receiver", "receiving"),
    "adv_defensive": _adv("defensive"),
    "adv_turnover": _adv("turnover"),
    "adv_drives": _adv("drives"),
    "adv_situational": _adv("situational"),
    "adv_defensive_players": _adv("defensive_players"),
    "adv_specialists": _adv("specialists"),
}

#: usage / situational sections (sportsdataverse.football.usage_box), per game
#: and as season leaderboards
_USAGE_SECTIONS = (
    ("player_usage", "player_usage", "players"),
    ("position_group_usage", "position_group_usage", "position_groups"),
    ("tackles", "tackles", "tackles"),
    ("position_group_tackles", "position_group_tackles", "position_group_tackles"),
    ("team_usage", "team_usage", "teams"),
    ("drive_scripting", "drive_scripting", "drive_scripting"),
    ("st_kickers", "st_kickers", "st_kickers"),
    ("st_punters", "st_punters", "st_punters"),
    ("st_returners", "st_returners", "st_returners"),
    ("st_blocks", "st_blocks", "st_blocks"),
    ("st_team", "st_team", "st_team"),
)
for _section, _adv_key, _lb_key in _USAGE_SECTIONS:
    REGISTRY[f"adv_{_adv_key}"] = DatasetSpec(
        f"adv_{_adv_key}", f"adv_{_adv_key}", f"espn_nfl_adv_{_adv_key}", usage_section=_section
    )
    REGISTRY[f"usage_{_lb_key}"] = DatasetSpec(
        f"usage_{_lb_key}",
        f"usage_{_lb_key}",
        f"espn_nfl_usage_{_lb_key}",
        usage_section=_section,
        aggregate=True,
    )

#: team / coach tendencies (sportsdataverse.football.tendencies), shims 61-63
REGISTRY["team_tendencies"] = DatasetSpec(
    "team_tendencies", "team_tendencies", "espn_nfl_team_tendencies", tendencies="team"
)
REGISTRY["coach_tendencies"] = DatasetSpec(
    "coach_tendencies", "coach_tendencies", "espn_nfl_coach_tendencies", tendencies="coach"
)
REGISTRY["coach_careers"] = DatasetSpec(
    "coach_careers", "coach_careers", "espn_nfl_coach_careers", tendencies="careers"
)

#: The ten advanced-box datasets, in the cfb stage-04 order.
ADV_ORDER: list[str] = [
    "adv_team",
    "adv_passing",
    "adv_rushing",
    "adv_receiving",
    "adv_defensive",
    "adv_turnover",
    "adv_drives",
    "adv_situational",
    "adv_defensive_players",
    "adv_specialists",
]

#: The eleven per-game usage / special-teams datasets (shims 30-40) and their season leaderboards (50-60).
USAGE_ADV_ORDER: list[str] = [f"adv_{k}" for _, k, _ in _USAGE_SECTIONS]
USAGE_LEADERBOARD_ORDER: list[str] = [f"usage_{k}" for _, _, k in _USAGE_SECTIONS]

#: Team then coach seasons, then careers (which reads the written coach seasons).
TENDENCIES_ORDER: list[str] = ["team_tendencies", "coach_tendencies", "coach_careers"]

#: Build order for a full run (the numbered shims in ``python/`` follow it).
ALL_ORDER: list[str] = [
    "pbp",
    "team_box",
    "player_box",
    *ADV_ORDER,
    "play_participants",
    "drives",
    *USAGE_ADV_ORDER,
    *USAGE_LEADERBOARD_ORDER,
    *TENDENCIES_ORDER,
]
