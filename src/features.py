"""Per-frame features from the aligned observations. Vectorised, metres and seconds throughout.

Nothing here decides anything: these are measurements. Combining them into evidence scores is
evidence.py's job, and temporal reasoning about them is decoder.py's.
"""

from dataclasses import dataclass

import numpy as np

from src.config import CONFIG, seconds_to_frames
from src.io.atd import AWAY, HOME


@dataclass
class Features:
    dist: np.ndarray           # (n, 2) float32: nearest valid player distance per team, metres;
                               # inf where the ball or every player of that team is unobserved
    proximity: np.ndarray      # (n, 2) float32 in [0, 1]: 1 at contact, 0 at soft_radius_m
    in_control_range: np.ndarray  # (n, 2) bool: nearest player within control_radius_m
    persistence: np.ndarray    # (n, 2) float32 in [0, 1]: trailing fraction of recent frames
                               # with that team in control range
    ball_stationary: np.ndarray   # (n,) bool: seen, plausible and slower than the threshold
    out_of_bounds: np.ndarray     # (n,) bool: seen, plausible and beyond a line by the margin
    unattended: np.ndarray        # (n,) bool: seen and nobody from either team within soft radius


def trailing_mean(values, window_frames):
    """Mean of the last `window_frames` values at each position, O(n) via cumulative sums."""
    padded = np.concatenate(([0.0], np.cumsum(values, dtype=np.float64)))
    index = np.arange(len(values))
    low = np.maximum(0, index + 1 - window_frames)
    return ((padded[index + 1] - padded[low]) / (index + 1 - low)).astype(np.float32)


def compute_features(tracking, quality, cfg=CONFIG.features, fps=25):
    length, width = tracking.pitch

    # Distances from the ball to every slot, with unusable observations pushed to inf.
    delta = tracking.players_xy - tracking.ball_xy[:, None, :]
    all_dist = np.sqrt(np.sum(delta * delta, axis=2, dtype=np.float32))
    usable = quality.ball_plausible[:, None] & ~np.isnan(all_dist)
    all_dist = np.where(usable, all_dist, np.float32(np.inf))

    dist = np.stack(
        [all_dist[:, tracking.team_of_slot == team].min(axis=1) for team in (HOME, AWAY)],
        axis=1)

    proximity = np.clip(1.0 - dist / cfg.soft_radius_m, 0.0, 1.0).astype(np.float32)
    in_control_range = dist <= cfg.control_radius_m

    window = seconds_to_frames(cfg.persistence_window_s, fps)
    persistence = np.stack(
        [trailing_mean(in_control_range[:, team].astype(np.float32), window)
         for team in (HOME, AWAY)], axis=1)

    plausible = quality.ball_plausible
    ball_stationary = plausible & (quality.ball_speed < cfg.stationary_speed_mps)

    x, y = tracking.ball_xy[:, 0], tracking.ball_xy[:, 1]
    margin = cfg.boundary_margin_m
    out_of_bounds = plausible & ((x < -margin) | (x > length + margin)
                                 | (y < -margin) | (y > width + margin))

    unattended = quality.ball_seen & np.isinf(dist).all(axis=1)

    return Features(dist=dist, proximity=proximity, in_control_range=in_control_range,
                    persistence=persistence, ball_stationary=ball_stationary,
                    out_of_bounds=out_of_bounds, unattended=unattended)
