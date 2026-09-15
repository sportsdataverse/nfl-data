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

from dataclasses import dataclass
from importlib import metadata

#: Bumped when the final payload's shape or semantics change for reasons a
#: sdv-py release number does not capture (a new embedded block, a changed
#: key, a processor fix landed on git main). Cached finals whose
#: ``processing_version`` differs are reprocessed.
#: 2: NFLPlayProcess scoring_opp read the home-oriented start.yardLine
#:    instead of start.yardsToEndzone (sportsdataverse-py, 2026-09-15).
SCHEMA_REV = 2


def processing_version() -> str:
    """``<sdv-py version>+<SCHEMA_REV>`` stamped on every cached final."""
    try:
        sdv = metadata.version("sportsdataverse")
    except metadata.PackageNotFoundError:  # pragma: no cover - editable oddities
        sdv = "unknown"
    return f"{sdv}+{SCHEMA_REV}"


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

#: Build order for a full run (the numbered shims in ``python/`` follow it).
ALL_ORDER: list[str] = [
    "pbp",
    "team_box",
    "player_box",
    *ADV_ORDER,
    "play_participants",
    "drives",
]
