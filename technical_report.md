# Technical Report — Frame-Level Football Possession

**Repository:** [matheusschreiber/more-than-a-hack-2027-barcelona](https://github.com/matheusschreiber/more-than-a-hack-2027-barcelona)  
**Task:** label each tactical-video frame as home possession (`H`), away possession (`A`), dead ball (`D`), or abstention (`X`).

## 1. Approach

We use a deterministic, evidence-based pipeline rather than training a classifier. The provided tracking already gives player and ball positions, so the main challenge is deciding when proximity represents controlled possession rather than a pass, deflection, loose ball, or tracking error. A rule-based temporal decoder is also easier to inspect and reproduce on this single-match task than a learned model with no independent labelled training set.

The pipeline has five stages:

1. **Load and align tracking.** Parse the tactical ATD metadata and raw tracking file. Convert the 1-based ATD frame IDs to 0-based video frames, map track slots to the two teams, and scale normalised coordinates into metres. Missing records remain missing; duplicate and out-of-range frame IDs are rejected.
2. **Estimate observation quality.** Reject implausible ball jumps above 45 m/s. Reliability combines ball-observation recency (linear decay over four seconds) with the number of visible player tracks for the less well-covered team (seven tracks is the full-coverage reference).
3. **Build control and stoppage features.** For each side, calculate the nearest tracked-player distance to the ball, a proximity score (full at contact, falling to zero at 6 m), and the fraction of the previous 1.2 seconds in which a player was within 2 m. Also calculate ball speed, whether it is outside the pitch by more than 0.5 m, and whether player-distance observations are unavailable.
4. **Combine evidence.** Team-control evidence is `0.6 × proximity + 0.4 × persistence + 0.15 × team-tag prior`, multiplied by tracking reliability. Dead-ball evidence combines out-of-bounds (`0.7`), a set-piece tag (`0.45`), and a stationary-ball/absence-of-player-observations cue (`0.35`). Missing ball observations do not themselves count as dead-ball evidence. Smart Tagging contributes only a bounded prior; overlapping tags do not stack.
5. **Decode the timeline.** A temporal state machine holds the current team through short ambiguity, requires sustained opposing evidence to confirm a turnover, and enters/exits `D` using separate stoppage and restart tests. Confirmed changes are backdated to the first supporting frame, so the output does not include the confirmation delay.

The reference nearest-player/majority-vote baseline was used as a starting point, but the final pipeline adds quality weighting, tactical context, explicit dead-ball evidence, and stateful transition logic.

## 2. Assets used and omitted

**Used**

- **Tactical ATD metadata and raw tracking** (`BAR-ATH_tactical_atd.xml` and `BAR-ATH_tactical_atd.txt`): the source of player positions, ball positions, team membership, and frame alignment. Track slots are treated as temporary tracklets, not persistent player identities.
- **Tactical Smart Tagging XML** (`BAR-ATH_tactical_smart_tagging.xml`): team-bearing phase intervals provide a small possession prior; `SET PIECES` intervals provide weak stoppage context. Unknown/`N/A` teams are not guessed.

**Not used by the final pipeline**

- Tactical video (`BAR-ATH_tactical.mp4`): no image/video model or manual video annotation is used.
- Tactical homography CSV: not required because ATD positions are already in pitch coordinates and are converted directly to metres.
- Broadcast video, broadcast ATD, and broadcast homography: omitted because the broadcast timeline has cuts/replays and is not synchronised to the tactical frame sequence. No attempt to align it is implemented.

The repository does not document experiments with these omitted assets, so they are described as unused rather than as approaches tested and rejected.

## 3. Training data

**No labelled training dataset is used (zero training examples); the pipeline has no fitted or supervised model.** There is no external labelled dataset, and no labels from the full competition match are used to train the pipeline.

The repository includes the challenge's public five-minute reference labels (7,500 graded frames). The project roadmap treats these as a pipeline/file-alignment sanity check only, not as training data or a tuning set. The challenge documentation says the reference is mechanically derived from corrected tracking. It is part of the provided game and is not used to fit model parameters. No additional annotator-created labels are declared in the repository.

## 4. Possession rules

- **Loose balls and challenges:** possession stays with the current team through brief ambiguity. A touch, deflection, or contested ball does not automatically transfer possession. A turnover candidate must show opposing-team evidence of at least `0.50`, exceed the current team's evidence by at least `0.15`, and persist for `0.8 s`. It is cancelled if the opposing score collapses to `0.25` or below. This is a tracking-based proxy for controlled possession; there is no separate aerial-duel or tackle classifier.
- **Starting possession:** from an unresolved state, a team must reach `0.55` evidence for `0.6 s`. Frames are assigned from the candidate's onset once confirmed.
- **Dead ball:** `D` requires affirmative dead-ball evidence of at least `0.55`, stronger than either team's control evidence, for `1.0 s`. Out-of-bounds evidence can cross the threshold by itself; a set-piece tag or the idle-ball cue alone cannot. Missing ball data alone never means `D`.
- **Restarts:** a `D` state ends only when team evidence reaches `0.50` while dead-ball evidence has fallen below `0.55` for `0.6 s`. The restarting team is inferred from the control evidence; the code does not assume that the tagged team or the home team always restarts. Until a side is supported, the output remains `D`.
- **Abstention and half-time:** each half is decoded independently. Frames outside the two match halves are `X`. During live play, reliability below `0.20` for more than `8 s` returns the decoder to unresolved (`X`) rather than carrying a possibly stale possession indefinitely.

## 5. Limitations and next steps

- The method is heuristic and uses fixed thresholds; it has no learned calibration and is demonstrated on one match. Thresholds may not transfer cleanly to different tracking quality, camera setups, or playing styles.
- The ball is missing on roughly 41% of the graded frames in the supplied match. The pipeline does not interpolate the ball or recover it from video, so long gaps can lead to abstention and a turnover hidden inside a gap can be missed.
- Nearest-player distance and short-window persistence are imperfect proxies for control. The code does not explicitly model passes, ball flight, aerial duels, tackles, pressure, player velocity, or team shape; close challenges and rebounds can therefore be misread.
- The current `unattended` feature is implemented as *no usable player-distance observation for either team*, not simply “no player within 6 m”. This makes the stationary-ball dead cue conservative, but also means it depends on missing player tracks.
- The roadmap still lists several synthetic edge-case tests as pending, including turnovers hidden by missing-ball gaps and same-team/opponent-team restart cases. The repository does not publish a documented score for this pipeline; the upstream starter-baseline score should not be presented as this system's result.

With more time, I would add automated synthetic tests for all transition cases, validate thresholds on independently labelled matches (never this competition match), and add collective motion/ball-trajectory features. I would only add video or broadcast processing after implementing and validating frame synchronisation and a clear ball-recovery experiment.

## 6. Reproduction

The match bundle must be obtained through the challenge registration process and unpacked locally; it is not included in the public repository. Keep the supplied filenames and place the tactical assets under `data/tactical/` as described in the challenge `DATA.md`.

Use Python **3.10 or newer** (the source uses `str | None` type syntax). From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python3 -m pip install -r requirements.txt

# Generate the full frame-level file
python3 -m src.run --out outputs/team_name.csv

# Check format, then optionally score against the public five-minute reference
python3 evaluation/validate_submission.py outputs/team_name.csv
python3 evaluation/run_evaluation.py --results outputs --gt public
```

`python3 -m src.run` without `--out` writes `outputs/submission.csv`. Use `--data-dir /path/to/data` if the match bundle is stored elsewhere. The public reference score is for checking the pipeline only, not for selecting thresholds or tuning the method.

## Repository implementation references

- [`src/run.py`](https://github.com/matheusschreiber/more-than-a-hack-2027-barcelona/blob/main/src/run.py) — pipeline entry point and command-line options
- [`src/config.py`](https://github.com/matheusschreiber/more-than-a-hack-2027-barcelona/blob/main/src/config.py) — thresholds and temporal windows
- [`src/io/atd.py`](https://github.com/matheusschreiber/more-than-a-hack-2027-barcelona/blob/main/src/io/atd.py), [`src/io/tags.py`](https://github.com/matheusschreiber/more-than-a-hack-2027-barcelona/blob/main/src/io/tags.py) — input parsing
- [`src/quality.py`](https://github.com/matheusschreiber/more-than-a-hack-2027-barcelona/blob/main/src/quality.py), [`src/features.py`](https://github.com/matheusschreiber/more-than-a-hack-2027-barcelona/blob/main/src/features.py), [`src/evidence.py`](https://github.com/matheusschreiber/more-than-a-hack-2027-barcelona/blob/main/src/evidence.py), [`src/decoder.py`](https://github.com/matheusschreiber/more-than-a-hack-2027-barcelona/blob/main/src/decoder.py) — scoring and temporal logic
- [`src/step-by-step.md`](https://github.com/matheusschreiber/more-than-a-hack-2027-barcelona/blob/main/src/step-by-step.md) — implementation roadmap and remaining tests
- [Challenge data description](https://github.com/matheusschreiber/more-than-a-hack-2027-barcelona/blob/main/DATA.md), [possession definition](https://github.com/matheusschreiber/more-than-a-hack-2027-barcelona/blob/main/CHALLENGE.md), and [rules](https://github.com/matheusschreiber/more-than-a-hack-2027-barcelona/blob/main/RULES.md)
