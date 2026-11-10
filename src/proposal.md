# Proposal: tracking-based possession with temporal reasoning

## Goal and scope

The idea is to build an offline system that converts the automatic tactical tracking and Smart Tagging into one possession label per tactical-video frame. The first version needs no neural network, labelled training set, or video decoding.

The output is a `frame,label` CSV with 199,319 rows, indexed from 0 to 199318:

- `H`: home team in possession while the ball is in play.
- `A`: away team in possession while the ball is in play.
- `D`: dead ball, regardless of which team will restart.
- `X`: abstention, also used outside the published graded intervals.

This is a proposal, not an implemented or validated system. The implementation roadmap is in [step-by-step.md](step-by-step.md).

## Main roadmap

We will build the decision logic incrementally, starting with clear tracking observations and progressively addressing contested balls, brief touches, and missing detections. At each frame, weighted features will produce evidence scores for home control, away control, and dead ball, with unreliable observations reducing confidence rather than implying a stoppage. A temporal state machine will use these scores, their persistence, and the previous state to distinguish genuine possession changes and restarts from momentary noise, producing one label per frame or abstaining when evidence is insufficient.

## Why this approach

The supplied baseline chooses the player nearest the ball and smooths the result. It is useful but confuses missing observations with stoppages and does not distinguish a touch from controlled possession.

Our working hypothesis is that separating observation quality, team control, and stoppage evidence will reduce false transitions without delaying genuine changes excessively. Synthetic sequences can test these behaviors cheaply; performance improvements require independent labelled matches to establish.

The ranking metric, `spellF1`, matches possession intervals rather than counting correct frames alone. Stability matters, but indiscriminate smoothing can erase short possessions or move their boundaries. We therefore model transitions explicitly rather than simply increasing a majority-vote window.

## Features

Features at the original 25 fps, with rolling windows expressed in seconds and converted to frames through one shared configuration.

| Feature group | Examples | Purpose |
| --- | --- | --- |
| Observation quality | Ball observed flag, gap age, plausible motion, player coverage | Decide how much evidence to trust |
| Ball proximity | Nearest valid player distance per team, difference between teams | Candidate controller |
| Control continuity | Repeated close support from one team, persistence of its advantage | Separate sustained control from a touch |
| Ball dynamics | Speed, direction change, separation from nearby players | Identify movement and possible exchanges |
| Team context | Local support near the ball, robust spread and collective movement | Supporting context during ambiguity |
| Boundary context | Ball near or outside pitch limits with uncertainty | Supporting stoppage evidence |
| Tag context | Team-bearing phases, set-piece types and nearby intervals | Soft team and restart priors |

No feature is decisive alone. A stationary ball may be under live control; an apparent out-of-bounds point may be tracking noise. During aerial play, ground plane proximity is especially unreliable.

## Temporal State Machine

The goal is (initially) a deterministic state machine over `H`, `A`, and `D`, with an internal unresolved condition when evidence cannot initialize a state.

- While live, preserve the current team through brief ambiguity or loss of the ball track. Weaken confidence as a gap grows; do not retain certainty forever.
- Open a turnover candidate when the opposing team has credible control evidence. Confirm it only when that evidence persists; cancel it if the evidence collapses.
- Record the candidate onset. Because inference is offline, a confirmed transition can be assigned to that onset rather than delayed by the confirmation window.
- Enter `D` only with affirmative stoppage evidence. Detect the restart separately using credible movement/control and restart context, then initialize the team.
- Use different entry and exit thresholds, where justified, to prevent flicker. Do not impose a universal minimum duration that erases legitimate short spells.
- Reset all history at each half. Never carry the first-half owner through halftime.

Emit `X` when unresolved evidence cannot support a state, especially at half initialization or extended gaps. Track its cost explicitly: `macroF1` counts it as a miss; `spellF1` fills it within each half, so it does not solve uncertain transitions. Prefer defensible explicit labels rather than optimizing abstentions.

Only if the state machine proves inadequate, consider a three-state HMM/Viterbi decoder with observation scores and transition costs. It must still account for quality and restarts. It is an optional replacement, not a second mandatory layer.

## Diagnostics and validation

Alongside the tracking and labeling, we will keep private summaries of label counts, segment lengths, abstentions, and behavior during missing-ball gaps. These reveal pathologies but are not substitutes for labelled evaluation or targets for forced possession counts.

Also, it is important to test alignment, geometry, missingness, half isolation, and temporal behavior with small synthetic fixtures. On independent labelled matches, evaluate `spellF1`, `macroF1`, stoppages, fragmentation, and boundary timing, keeping whole matches separate for development and evaluation where possible.

The challenge's public labels are used only for pipeline sanity checks, not training, tuning, or choosing variants.