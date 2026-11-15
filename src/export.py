"""Write the official submission CSV and nothing else in it.

The contract (SUBMISSION.md): a 'frame,label' header, one row per tactical video frame, frames
0..n-1 in order, labels in {H, A, D, X}, no blank cells. Diagnostics belong in a separate file,
never in this one.
"""

import os

import numpy as np

LEGAL_LABELS = frozenset("HADX")


def write_submission(path, labels):
    """Write the CSV, creating the output folder. Refuses illegal labels rather than guessing."""
    illegal = sorted(set(np.unique(labels)) - LEGAL_LABELS)
    if illegal:
        raise ValueError(f"illegal labels {illegal}; legal are H, A, D, X")

    folder = os.path.dirname(os.path.abspath(path))
    os.makedirs(folder, exist_ok=True)
    with open(path, "w") as handle:
        handle.write("frame,label\n")
        handle.writelines(f"{frame},{label}\n"
                          for frame, label in enumerate(labels))
    return path


def label_counts(labels):
    """{label: count} over the legal alphabet, for printing."""
    return {label: int(np.sum(labels == label)) for label in "HADX"}
