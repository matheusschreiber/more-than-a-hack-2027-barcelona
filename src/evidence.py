"""Combine features, quality and tag context into per-frame evidence scores.

Four series in [0, 1]: home control, away control, dead ball, and reliability. The conventions
the roadmap demands are enforced here, in one place:

  * unreliable observations weaken team-control evidence (multiplied by reliability); they
    never add dead-ball evidence -- a missing ball contributes exactly nothing to `dead`
  * tags are soft context: the team prior is one small bounded term, and a set-piece window
    alone stays below the decoder's dead threshold, so a restart tag cannot dictate its interval
  * every dead-ball cue is affirmative (out of bounds, tagged set piece, an idle unattended
    ball) and the total is capped at 1
"""

from dataclasses import dataclass

import numpy as np

from src.config import CONFIG
from src.io.atd import AWAY, HOME
from src.io.tags import set_piece_mask, team_phase_masks


@dataclass
class Evidence:
    home: np.ndarray         # (n,) float32 in [0, 1]
    away: np.ndarray         # (n,) float32 in [0, 1]
    dead: np.ndarray         # (n,) float32 in [0, 1]
    reliability: np.ndarray  # (n,) float32 in [0, 1], passed through for the decoder


def compute_evidence(features, quality, tag_intervals, n_frames, cfg=CONFIG.evidence):
    home_tag, away_tag = team_phase_masks(tag_intervals, n_frames)
    set_piece = set_piece_mask(tag_intervals, n_frames)

    def team_score(team, tag_mask):
        raw = (cfg.proximity_weight * features.proximity[:, team]
               + cfg.persistence_weight * features.persistence[:, team]
               + cfg.tag_prior_weight * tag_mask)
        return (np.clip(raw, 0.0, 1.0) * quality.reliability).astype(np.float32)

    idle = features.ball_stationary & features.unattended
    dead = np.clip(cfg.out_of_bounds_weight * features.out_of_bounds
                   + cfg.set_piece_tag_weight * set_piece
                   + cfg.idle_ball_weight * idle, 0.0, 1.0).astype(np.float32)

    return Evidence(home=team_score(HOME, home_tag), away=team_score(AWAY, away_tag),
                    dead=dead, reliability=quality.reliability)
