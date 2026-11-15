"""Run the whole pipeline: tracking in, submission CSV out.

    python -m src.run                                  # writes outputs/submission.csv
    python -m src.run --out outputs/team_name.csv

Then check and score it with the official tooling:

    python evaluation/validate_submission.py outputs/submission.csv
    python evaluation/run_evaluation.py --results outputs --gt public

Reading the raw ATD takes a minute or two -- it streams 199319 lines of tracking.
"""

import argparse
import os
import sys

if __package__ in (None, ""):  # allow `python src/run.py` as well as `python -m src.run`
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src
from games import GAME, GAMES
from src.config import CONFIG
from src.decoder import decode
from src.evidence import compute_evidence
from src.export import label_counts, write_submission
from src.features import compute_features
from src.io.atd import load_tracking
from src.io.tags import load_tag_intervals
from src.quality import compute_quality

DEFAULT_OUT = os.path.join(src.ROOT, "outputs", "submission.csv")


def run(game=GAME, data_dir=None, out_path=DEFAULT_OUT):
    fps = GAMES[game]["fps"]

    print(f"config {CONFIG.version} | game {game}")
    print("reading tracking ...")
    tracking = load_tracking(game, data_dir)
    print(f"  teams: H = {tracking.home_name}, A = {tracking.away_name}")
    print(f"  {tracking.n_frames} frames, {int((~tracking.record_seen).sum())} without an ATD record")

    quality = compute_quality(tracking, CONFIG.quality, fps)
    seen = int(quality.ball_seen.sum())
    print(f"  ball seen on {seen} frames ({100.0 * seen / tracking.n_frames:.1f}%), {int((quality.ball_seen & ~quality.ball_plausible).sum())} implausible jumps")

    intervals = load_tag_intervals(tracking.home_name, tracking.away_name, game, data_dir)
    print(f"  {len(intervals)} smart-tagging intervals")

    features = compute_features(tracking, quality, CONFIG.features, fps)
    evidence = compute_evidence(features, quality, intervals, tracking.n_frames,
                                CONFIG.evidence)
    labels = decode(evidence, game, CONFIG.decoder, fps)

    path = write_submission(out_path, labels)
    counts = label_counts(labels)
    print(f"\nwrote {os.path.relpath(path, src.ROOT)}")
    print("  " + "  ".join(f"{k} {v:>7}" for k, v in counts.items()))
    print("\nNext:")
    print(f"  python evaluation/validate_submission.py {os.path.relpath(path)}")
    print(f"  python evaluation/run_evaluation.py --results {os.path.relpath(os.path.dirname(path))} --gt public")
    return labels


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--game", default=GAME)
    parser.add_argument("--data-dir", default=None,
                        help="override the data directory (default: games.DATA_DIR)")
    parser.add_argument("--out", default=DEFAULT_OUT, help="where to write the submission CSV")
    args = parser.parse_args()
    run(args.game, args.data_dir, args.out)
