"""Smart Tagging intervals on the tactical timeline, normalised and mapped to sides.

Parsing follows starter/load_smart_tagging.py, whose check_time_base() verified on the delivered
file that <start>/<end> are seconds from the first frame of the tactical video, so seconds x fps
is a video frame directly. Intervals stay half-open on the right, the way the rest of the
repository treats intervals.

What is added on top of the starter loader:

  * strings are stripped and matched case-insensitively, and "N/A" collapses to None
  * the Team tag names a club; here it is mapped to a side (H/A) through the ATD metadata names
  * per-frame masks whose contribution is inherently capped -- a frame covered by five
    overlapping team-bearing phases counts exactly once

These tags are automatic annotation, not ground truth: phases are not possessions and a tagged
restart is a window around the event, not the instant of it. They only ever feed *soft* evidence.
"""

import xml.etree.ElementTree as ET
from dataclasses import dataclass

import numpy as np

import src  # noqa: F401  (puts the repository root on sys.path)
from games import GAME, GAMES, require

SET_PIECE_CODE = "set pieces"
NOT_AVAILABLE = {"", "n/a", "na", "none"}


@dataclass
class TagInterval:
    code: str                 # normalised lower-case code, e.g. "set pieces"
    start_frame: int          # inclusive
    end_frame: int            # exclusive (half-open)
    side: str | None          # "H", "A", or None when the Team tag is absent/unknown
    half: str | None          # the Half tag text, if any
    type: str | None          # the Type tag text (e.g. a set-piece kind), if any


def _clean(text):
    text = (text or "").strip()
    return None if text.lower() in NOT_AVAILABLE else text


def load_tag_intervals(home_name, away_name, game=GAME, data_dir=None, fps=None):
    """[TagInterval] in file order. Unknown team names map to side None, never to a guess."""
    fps = fps or GAMES[game]["fps"]
    path = require(["smart_tagging"], game, data_dir)[0]
    sides = {home_name.strip().lower(): "H", away_name.strip().lower(): "A"}

    out = []
    for instance in ET.parse(path).getroot().iter("instance"):
        start_s = float(instance.findtext("start"))
        end_s = float(instance.findtext("end"))
        tags = {(label.findtext("group") or "").strip(): _clean(label.findtext("text"))
                for label in instance.findall("label")}
        team = tags.get("Team")
        out.append(TagInterval(
            code=(_clean(instance.findtext("code")) or "").lower(),
            start_frame=round(start_s * fps),
            end_frame=round(end_s * fps),
            side=sides.get(team.lower()) if team else None,
            half=tags.get("Half"),
            type=tags.get("Type"),
        ))
    return out


def _paint(mask, intervals):
    n = len(mask)
    for interval in intervals:
        start = max(0, interval.start_frame)
        end = min(n, interval.end_frame)
        if start < end:
            mask[start:end] = True
    return mask


def team_phase_masks(intervals, n_frames):
    """(home, away) boolean masks: frames covered by at least one team-bearing phase.

    Boolean coverage rather than a count is the overlap cap: however many phases agree on a
    frame, the prior there is the same.
    """
    home = np.zeros(n_frames, dtype=bool)
    away = np.zeros(n_frames, dtype=bool)
    _paint(home, [i for i in intervals if i.side == "H" and i.code != SET_PIECE_CODE])
    _paint(away, [i for i in intervals if i.side == "A" and i.code != SET_PIECE_CODE])
    return home, away


def set_piece_mask(intervals, n_frames):
    """Boolean mask of frames inside any tagged set-piece window: soft stoppage context."""
    return _paint(np.zeros(n_frames, dtype=bool),
                  [i for i in intervals if i.code == SET_PIECE_CODE])
