"""Deterministic temporal state machine: evidence scores in, one label per frame out.

States are H, A, D plus an internal unresolved condition that emits X. The rules follow
proposal.md:

  * each half is decoded independently; everything outside the half blocks is X, and no state
    or window ever crosses halftime
  * while live, the current team is held through brief ambiguity; a turnover needs opposing
    evidence that clears a margin and persists, and the confirmed boundary is placed back at
    the candidate's onset -- offline inference pays no confirmation delay
  * D is entered only on persistent affirmative stoppage evidence, and left through a separate
    restart detector that decides the owner from evidence, with no home-team default
  * long effective blindness decays into abstention instead of coasting forever

There is deliberately no blanket minimum spell duration and no final smoothing pass.
"""

import numpy as np

import src  # noqa: F401  (puts the repository root on sys.path)
from games import GAME, GAMES, half_video_blocks
from src.config import CONFIG, seconds_to_frames

H, A, D, X = "H", "A", "D", "X"
UNRESOLVED = None


def decode(evidence, game=GAME, cfg=CONFIG.decoder, fps=None):
    """Labels for the whole tactical timeline: decoded inside each half block, X elsewhere."""
    fps = fps or GAMES[game]["fps"]
    n = len(evidence.home)
    labels = np.full(n, X, dtype="<U1")
    for _half, first, last in half_video_blocks(game):
        _decode_block(labels, evidence, max(first, 0), min(last, n - 1), cfg, fps)
    return labels


def _decode_block(labels, ev, first, last, cfg, fps):
    init_confirm = seconds_to_frames(cfg.init_confirm_s, fps)
    turnover_confirm = seconds_to_frames(cfg.turnover_confirm_s, fps)
    dead_confirm = seconds_to_frames(cfg.dead_confirm_s, fps)
    restart_confirm = seconds_to_frames(cfg.restart_confirm_s, fps)
    abstain_after = seconds_to_frames(cfg.abstain_after_s, fps)

    state = UNRESOLVED
    # Candidates are (team, onset frame, consecutive supporting frames). Onset is stored
    # separately from confirmation time so a confirmed change is written back to its onset.
    cand_team, cand_onset, cand_len = UNRESOLVED, 0, 0
    dead_onset, dead_len = 0, 0
    blind_len = 0

    for f in range(first, last + 1):
        h, a, d = ev.home[f], ev.away[f], ev.dead[f]
        best_team, best = (H, h) if h >= a else (A, a)

        # --- stoppage entry: affirmative, persistent, and stronger than any control reading.
        if state != D:
            if d >= cfg.dead_score and d > max(h, a):
                if dead_len == 0:
                    dead_onset = f
                dead_len += 1
            else:
                dead_len = 0
            if dead_len >= dead_confirm:
                labels[dead_onset:f + 1] = D
                state = D
                cand_team, cand_len = UNRESOLVED, 0
                dead_len = 0
                blind_len = 0
                continue

        if state == D:
            labels[f] = D
            # --- restart exit: credible control while the stoppage evidence has faded.
            # The owner comes from the evidence; an unknown owner just keeps waiting.
            if best >= cfg.restart_score and d < cfg.dead_score:
                if cand_len == 0 or cand_team != best_team:
                    cand_team, cand_onset, cand_len = best_team, f, 0
                cand_len += 1
            else:
                cand_len = 0
            if cand_len >= restart_confirm:
                labels[cand_onset:f + 1] = cand_team
                state = cand_team
                cand_team, cand_len = UNRESOLVED, 0
                blind_len = 0
            continue

        if state == UNRESOLVED:
            labels[f] = X
            if best >= cfg.init_score:
                if cand_len == 0 or cand_team != best_team:
                    cand_team, cand_onset, cand_len = best_team, f, 0
                cand_len += 1
            else:
                cand_len = 0
            if cand_len >= init_confirm:
                labels[cand_onset:f + 1] = cand_team
                state = cand_team
                cand_team, cand_len = UNRESOLVED, 0
                blind_len = 0
            continue

        # --- live possession: hold the state, watch for a turnover, decay when blind.
        labels[f] = state
        own, opp_score, opp = (h, a, A) if state == H else (a, h, H)

        if opp_score >= cfg.turnover_score and opp_score >= own + cfg.turnover_margin:
            if cand_len == 0 or cand_team != opp:
                cand_team, cand_onset, cand_len = opp, f, 0
            cand_len += 1
        elif opp_score <= cfg.turnover_cancel_score:
            # The evidence collapsed: the candidate is cancelled, not kept warm.
            cand_team, cand_len = UNRESOLVED, 0
        # Between cancel and confirm thresholds the candidate is held without growing.

        if cand_len >= turnover_confirm:
            labels[cand_onset:f + 1] = cand_team
            state = cand_team
            cand_team, cand_len = UNRESOLVED, 0
            blind_len = 0
            continue

        blind_len = blind_len + 1 if ev.reliability[f] < cfg.min_reliability else 0
        if blind_len >= abstain_after:
            # Effectively blind for too long: abstain from here on rather than coast. The
            # frames already written were held under decaying-but-present confidence and stand.
            state = UNRESOLVED
            cand_team, cand_len = UNRESOLVED, 0
            blind_len = 0
