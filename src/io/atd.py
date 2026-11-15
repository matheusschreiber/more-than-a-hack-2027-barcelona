"""Load the tactical ATD into aligned per-frame arrays, in metres, with validation. 

Parsing conventions follow starter/load_atd.py and starter/baseline.py, which verified them on
the delivered file:

  * one record per tactical video frame, frame_id counting from 1: video_frame = frame_id - 1
  * line format "<frame_id>:<player>;<player>;...:<ball>", each group "x,y,speed",
    with "NaN,NaN,NaN" for a missing observation
  * positions are normalised 0-1 and the pitch is anisotropic, so both axes are scaled to
    metres before anything measures a distance
  * slots are tracklets, not persons; the first team in the metadata XML is the home side; 
    slot 7 at minute 3 and slot 7 at minute 60 may be different players;

Unlike the baseline this keeps the positions, exposes missing records instead of shifting rows,
and rejects duplicate or out-of-range frame IDs outright.
"""

import xml.etree.ElementTree as ET
from dataclasses import dataclass

import numpy as np

import src  # noqa: F401  (puts the repository root on sys.path)
from games import GAME, GAMES, require, source_frames

FIELD_SEP = ":"
GROUP_SEP = ";"
MISSING = "N"  # first character of "NaN", which is all we need to test for

HOME, AWAY = 0, 1


@dataclass
class Tracking:
    """Everything downstream needs, aligned to the tactical video timeline (frame 0 based)."""

    players_xy: np.ndarray    # (n_frames, n_slots, 2) float32 metres, NaN where unobserved
    ball_xy: np.ndarray       # (n_frames, 2) float32 metres, NaN where unobserved
    team_of_slot: np.ndarray  # (n_slots,) int8, HOME or AWAY
    record_seen: np.ndarray   # (n_frames,) bool, False where the ATD had no record at all
    home_name: str
    away_name: str
    pitch: tuple              # (length_m, width_m)

    @property
    def n_frames(self):
        return len(self.ball_xy)


def team_of_each_track(meta_path):
    """Array over track slots: HOME if the slot belongs to the first team in the file, else AWAY.

    The first team in the FIFA/EPTS metadata is the home side -- the convention kloppy follows
    and DATA.md states independently for this match.
    """
    root = ET.parse(meta_path).getroot()
    team_ids = [team.get("id") for team in root.iter("Team")]
    if len(team_ids) != 2:
        raise ValueError(f"{meta_path}: expected 2 teams, found {len(team_ids)}")

    home_id = team_ids[0]
    slots = [player.get("teamId") for player in root.iter("Player")]
    if not slots:
        raise ValueError(f"{meta_path}: no Player entries")
    return np.array([HOME if team_id == home_id else AWAY for team_id in slots], dtype=np.int8)


def team_names(meta_path):
    """(home, away) club names, for mapping tags and for printing."""
    root = ET.parse(meta_path).getroot()
    names = tuple(team.findtext("Name") for team in root.iter("Team"))
    if len(names) != 2:
        raise ValueError(f"{meta_path}: expected 2 team names, found {len(names)}")
    return names


def load_tracking(game=GAME, data_dir=None):
    """Parse the raw ATD into a Tracking bundle. Raises on duplicates and out-of-range frames."""
    meta_path, raw_path = require(["atd_meta", "atd_raw"], game, data_dir)
    n_frames = source_frames("tactical", game)
    length, width = GAMES[game]["pitch"]

    team_of_slot = team_of_each_track(meta_path)
    home_name, away_name = team_names(meta_path)
    n_slots = len(team_of_slot)

    players_xy = np.full((n_frames, n_slots, 2), np.nan, dtype=np.float32)
    ball_xy = np.full((n_frames, 2), np.nan, dtype=np.float32)
    record_seen = np.zeros(n_frames, dtype=bool)

    with open(raw_path) as handle:
        for line_no, line in enumerate(handle, start=1):
            parts = line.split(FIELD_SEP)
            if len(parts) != 3:
                raise ValueError(f"{raw_path}:{line_no}: expected 3 ':'-separated fields, got {len(parts)}")

            frame = int(parts[0]) - 1  # frame_id counts from 1, submissions from 0
            if not 0 <= frame < n_frames:
                raise ValueError(f"{raw_path}:{line_no}: frame_id {frame + 1} outside 1..{n_frames}")
            if record_seen[frame]:
                raise ValueError(f"{raw_path}:{line_no}: duplicate record for frame_id {frame + 1}")
            record_seen[frame] = True

            groups = parts[1].split(GROUP_SEP)
            if len(groups) != n_slots:
                raise ValueError(f"{raw_path}:{line_no}: {len(groups)} player groups, metadata lists {n_slots} slots")
            for slot, group in enumerate(groups):
                if group[0] == MISSING:
                    continue
                x_text, y_text, _ = group.split(",", 2)
                players_xy[frame, slot, 0] = float(x_text) * length
                players_xy[frame, slot, 1] = float(y_text) * width

            ball = parts[2]
            if ball[0] != MISSING:
                x_text, y_text, _ = ball.split(",", 2)
                ball_xy[frame, 0] = float(x_text) * length
                ball_xy[frame, 1] = float(y_text) * width

    return Tracking(players_xy=players_xy, ball_xy=ball_xy, team_of_slot=team_of_slot,
                    record_seen=record_seen, home_name=home_name, away_name=away_name,
                    pitch=(length, width))
