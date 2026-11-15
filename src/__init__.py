"""Possession pipeline package. See proposal.md and step-by-step.md in this folder.

Importing this package puts the repository root on sys.path so that `games`, the shared
per-game constants module, resolves no matter where the interpreter was started.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
