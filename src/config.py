"""The one versioned configuration for the pipeline.

Every temporal window is expressed in seconds and converted to frames through
seconds_to_frames(), so the frame rate lives in games.py and nowhere here. Change a number,
bump the version, and the diagnostics written next to a submission say which configuration
produced it.
"""

from dataclasses import dataclass, field

CONFIG_VERSION = "0.1.0"


def seconds_to_frames(seconds, fps):
    """A window of `seconds` as a whole number of frames, never below 1."""
    return max(1, round(seconds * fps))


@dataclass(frozen=True)
class QualityConfig:
    # Above this the ball observation is treated as a tracking jump, not a ball in flight.
    max_plausible_ball_speed_mps: float = 45.0
    # Ball-recency confidence decays linearly from 1 to 0 across a gap of this many seconds.
    gap_decay_s: float = 4.0
    # Fewer valid slots than this on a team is poor coverage and lowers reliability.
    min_team_coverage: int = 7


@dataclass(frozen=True)
class FeatureConfig:
    # A player within this distance can plausibly control the ball.
    control_radius_m: float = 2.0
    # Proximity evidence decays to zero at this distance.
    soft_radius_m: float = 6.0
    # Trailing window for "this team has repeatedly been closest and in range".
    persistence_window_s: float = 1.2
    # Below this the ball counts as stationary.
    stationary_speed_mps: float = 0.5
    # The ball must be beyond a line by this much before it counts as out of bounds,
    # so touchline tracking noise does not read as a throw-in.
    boundary_margin_m: float = 0.5


@dataclass(frozen=True)
class EvidenceConfig:
    # Team control: instantaneous proximity vs sustained persistence.
    proximity_weight: float = 0.6
    persistence_weight: float = 0.4
    # Soft prior from team-bearing Smart Tagging phases. Deliberately small and applied once
    # per frame regardless of how many phases overlap, so tags cannot overwhelm tracking.
    tag_prior_weight: float = 0.15
    # Dead-ball evidence weights. Each one is affirmative: a missing ball contributes nothing.
    # Out of bounds is deliberately strong enough to cross the decoder's dead threshold alone;
    # the tag and idle cues are not, and need corroboration.
    out_of_bounds_weight: float = 0.7
    set_piece_tag_weight: float = 0.45
    idle_ball_weight: float = 0.35


@dataclass(frozen=True)
class DecoderConfig:
    # Initialization from unresolved: a team must hold this score for this long.
    init_score: float = 0.55
    init_confirm_s: float = 0.6
    # Turnover: opposing evidence must clear a score, a margin over the holder, and persist.
    turnover_score: float = 0.50
    turnover_margin: float = 0.15
    turnover_confirm_s: float = 0.8
    # A candidate whose evidence collapses below this is cancelled, not confirmed later.
    turnover_cancel_score: float = 0.25
    # Stoppage entry needs affirmative evidence that persists; restart exit is separate.
    dead_score: float = 0.55
    dead_confirm_s: float = 1.0
    restart_score: float = 0.50
    restart_confirm_s: float = 0.6
    # Reliability below this counts as "effectively blind".
    min_reliability: float = 0.2
    # Blind for this long while live -> abstain (X) rather than coast forever.
    abstain_after_s: float = 8.0


@dataclass(frozen=True)
class PipelineConfig:
    version: str = CONFIG_VERSION
    quality: QualityConfig = field(default_factory=QualityConfig)
    features: FeatureConfig = field(default_factory=FeatureConfig)
    evidence: EvidenceConfig = field(default_factory=EvidenceConfig)
    decoder: DecoderConfig = field(default_factory=DecoderConfig)


CONFIG = PipelineConfig()
