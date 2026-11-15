"""Observation-quality masks: how much the tracking can be trusted, frame by frame.

The point of this layer is the separation the proposal insists on: "the tracking went blind" is
a statement about observation quality, never direct evidence of a stoppage. Everything here is
descriptive -- nothing is interpolated or rewritten.
"""

from dataclasses import dataclass

import numpy as np

from src.config import CONFIG
from src.io.atd import AWAY, HOME


@dataclass
class Quality:
    ball_seen: np.ndarray        # (n,) bool
    gap_age: np.ndarray          # (n,) int32: frames since the ball was last seen (0 when seen)
    ball_speed: np.ndarray       # (n,) float32 m/s across the gap to the previous sighting;
                                 # NaN where unseen or where there is no previous sighting
    ball_plausible: np.ndarray   # (n,) bool: seen and not arriving by an implausible jump
    team_coverage: np.ndarray    # (n, 2) int16 valid slots per team (columns HOME, AWAY)
    reliability: np.ndarray      # (n,) float32 in [0, 1]


def compute_quality(tracking, cfg=CONFIG.quality, fps=25):
    ball_seen = ~np.isnan(tracking.ball_xy[:, 0])
    n = len(ball_seen)
    index = np.arange(n)

    # Index of the most recent sighting at or before each frame, -1 before the first one.
    last_seen = np.maximum.accumulate(np.where(ball_seen, index, -1))
    gap_age = np.where(last_seen >= 0, index - last_seen, index + 1).astype(np.int32)

    # Speed across the gap between consecutive sightings, assigned to the later sighting.
    ball_speed = np.full(n, np.nan, dtype=np.float32)
    seen_idx = np.flatnonzero(ball_seen)
    if len(seen_idx) > 1:
        step = np.diff(seen_idx)
        travel = np.linalg.norm(
            np.diff(tracking.ball_xy[seen_idx], axis=0), axis=1)
        ball_speed[seen_idx[1:]] = travel / (step / float(fps))

    # The first sighting of the file has no speed; treat it as plausible rather than suspect.
    ball_plausible = ball_seen & ~(ball_speed > cfg.max_plausible_ball_speed_mps)

    player_seen = ~np.isnan(tracking.players_xy[:, :, 0])
    team_coverage = np.stack(
        [player_seen[:, tracking.team_of_slot == team].sum(axis=1)
         for team in (HOME, AWAY)], axis=1).astype(np.int16)

    # Reliability: how recent the ball is, times how complete the player picture is. Low
    # reliability weakens control evidence downstream; it never argues for a dead ball.
    recency = np.clip(1.0 - gap_age / float(cfg.gap_decay_s * fps), 0.0, 1.0)
    coverage = np.clip(team_coverage.min(axis=1) / float(cfg.min_team_coverage), 0.0, 1.0)
    reliability = (recency * coverage).astype(np.float32)

    return Quality(ball_seen=ball_seen, gap_age=gap_age, ball_speed=ball_speed,
                   ball_plausible=ball_plausible, team_coverage=team_coverage,
                   reliability=reliability)
