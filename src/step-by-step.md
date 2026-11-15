# Roadmap: build the tracking and temporal pipeline

This is an implementation checklist, not a record of completed work. Follow [proposal.md](proposal.md) for the architecture. Finish a working end-to-end version before adding more advanced features.

## Prepare data and environment

- [x] Place data locally under the documented data directory or set `MTAH_DATA_DIR`.
- [x] Create an isolated environment and install [requirements.txt](../requirements.txt). Add [requirements-starter.txt](../requirements-starter.txt) only if using its loaders.
- [x] Verify asset availability using [games.py](../games.py), without hard-coded machine-specific paths.
- [x] Record the environment; pin the actual submission dependencies before release.

## Reproduce the baseline

```bash
python starter/baseline.py
python evaluation/validate_submission.py evaluation/results/baseline_smooth50.csv
```

- [x] Understand the metadata parser, meter-scaled distances, and CSV writer in [starter/baseline.py](../starter/baseline.py); reuse suitable logic.
- [x] Record its known limitation: missing ball observations become dead-ball labels when the smoothing window contains no team evidence.

## Establish implementation and test boundaries

- [x] Add a runnable pipeline entry point under `src/` and one versioned configuration.
- [x] Keep loading, features, evidence scoring, decoding, and export independently testable. Split modules only where this reduces complexity.

## Build the aligned observation layer

- [x] Load ATD and metadata through existing helpers or their established parsing conventions. Validate record counts, slot counts, frame range, and team IDs.
- [x] Allocate the entire tactical timeline; reject duplicate or out-of-range frame IDs and expose missing records instead of shifting subsequent rows.
- [x] Convert ATD frame IDs with `frame_id - 1` and positions to meters.
- [x] Load Smart Tagging with [starter/load_smart_tagging.py](../starter/load_smart_tagging.py). Normalize strings and handle `N/A`, unknown teams, and overlapping intervals.
- [x] Preserve half-open tag intervals and original frame indices throughout.
- [x] Reset temporal processing between the published graded intervals; output `X` elsewhere. Do not equate graded-interval starts with live kickoffs.
- [ ] Add tests for first/last frame alignment, anisotropic distance scaling, missing observations, tag rounding, and interval boundaries.

## Add quality masks and conservative cleanup

- [ ] Measure ball gaps, valid-player coverage, jumps, and possible duplicate tracks. 
- [x] Define general plausibility checks with explicit units and configuration. 
- [x] Keep raw, rejected, and interpolated observations distinguishable. 
- [ ] Optionally fill short plausible ball gaps; never bridge halves, long gaps, or suspected stoppages. Revisit interpolation after stoppage evidence exists.

## Implement features and evidence scores

- [x] Compute nearest valid player distance per team and the distance advantage. 
- [ ] Add repeated team proximity, plausible ball motion, local support, and rolling quality features. Keep windows in seconds in configuration. 
- [x] Avoid counting duplicate slots as independent support or assuming persistent player identities. 
- [x] Turn team-bearing tags into soft context; cap overlapping contributions so repeated phase annotations do not overwhelm tracking evidence.
- [ ] Add separate stoppage/restart context from boundary behavior, movement, inactivity, and set-piece tags. Require corroboration rather than a single cue. 
- [x] Produce home-control, away-control, dead-ball, and reliability scores with documented conventions for unavailable features.
- [ ] Test that missing ball data alone does not favor `D`, a stationary controlled ball can stay live, and a restart tag does not dictate its entire interval. 

## Implement the temporal decoder

- [x] Add `H`, `A`, `D`, and an internal unresolved initialization condition.
- [x] Retain the last controlling team through brief loose-ball and occlusion phases.
- [x] Track opposing-control candidates, confirm persistent evidence, and cancelcandidates that disappear. Store onset separately from confirmation time.
- [x] In offline output, assign a confirmed turnover to its supported onset ratherthan adding the full confirmation delay to the boundary.
- [x] Implement stoppage entry and restart exit separately; allow an unknown restartowner rather than inventing a home-team default.
- [x] Add confidence decay and an explicit abstention policy for long uncertainty.
- [x] Reset all state at half boundaries and keep windows from crossing them. 
- [x] Avoid blanket minimum spell durations or final smoothing that removes genuine short possessions. Keep the first implementation deterministic.

Required synthetic scenarios:

- [ ] Stable possession despite small nearest-player fluctuations.
- [ ] Pass or loose ball with no opposing controlled possession.
- [ ] A brief deflection that does not transfer possession.
- [ ] Sustained opposing control with a correctly placed turnover boundary.
- [ ] A credible short possession that is not erased automatically.
- [ ] Short and long missing-ball gaps, including a turnover hidden by a gap.
- [ ] Stoppage followed by a same-team or opposing-team restart.
- [ ] Unknown team tags, contradictory tags, and missing players from one team.
- [ ] Half initialization and halftime with no state leakage.

## Complete the end-to-end submission path

- [ ] Run automated tests; fix failures using their specified behavior.
- [x] Wire loading, features, scores, decoding, and export into one command.
- [x] Export exactly `frame,label`, ordered frames 0 through 199318, legal labels, no blank entries, and `X` outside the graded intervals.
- [ ] Write private diagnostic traces containing quality, scores, and transition reasons. Keep them separate from the official CSV.
- [x] Run the official validator on the exact generated file.

## Validate without turning public labels into a tuning set

- [x] Freeze a documented configuration before checking public labels. 
- [ ] Use public evaluation only to detect pipeline issues such as alignment or label-mapping mistakes, not to choose which algorithm or configuration to keep.
- [ ] Do not repeatedly score variants and select the best public result.
- [ ] Inspect raw observations and algorithm diagnostics to debug general logic, but do not save human decisions as labels, corrections, or frame-specific rules.

Existing commands, with `outputs/` containing only submission CSVs and with our
future entry point responsible for creating that directory:

```bash
python evaluation/validate_submission.py outputs/team_name.csv
python evaluation/run_evaluation.py --results outputs --gt public
```

## (bonus) Add complexity

- [ ] Consider an HMM/Viterbi decoder only if the state machine has a concrete limitation demonstrated by synthetic tests or independent labelled matches.
- [ ] Consider video-derived evidence only for an identified tracking failure. Keep broadcast synchronization and new detectors outside the minimum release.

## Final documentation

- [ ] Freeze dependencies, configuration, code version, and any random seeds.
- [ ] Document the actual entry-point command, required assets, installation, expected resource use, and all labelled or pseudo-labelled sources used.
- [ ] Regenerate in a clean environment with the licensed input assets available.
- [ ] Audit the public repository for licensed assets, caches, clipped video, reconstructive exports, private data, and machine-specific paths.
- [ ] Write the final technical report with the actual method, possession rules, assets used or dropped, limitations, evaluation evidence, and reproduction steps.