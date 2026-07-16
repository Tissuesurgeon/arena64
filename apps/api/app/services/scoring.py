"""Scoring helpers for Arena64 challenges."""


def score_answer(is_correct: bool, remaining_seconds: float) -> int:
    if not is_correct:
        return 0
    remaining = max(0.0, remaining_seconds)
    return 100 + int(remaining * 2)


def compare_tiebreak(
    fair_play_a: float,
    points_a: int,
    avg_time_a: float,
    fair_play_b: float,
    points_b: int,
    avg_time_b: float,
) -> int:
    """Return 1 if A wins tiebreak, -1 if B wins, 0 if still tied."""
    if fair_play_a != fair_play_b:
        return 1 if fair_play_a > fair_play_b else -1
    if points_a != points_b:
        return 1 if points_a > points_b else -1
    if avg_time_a != avg_time_b:
        return 1 if avg_time_a < avg_time_b else -1
    return 0


REWARD_SPLITS = {1: 0.55, 2: 0.25, 3: 0.12, 4: 0.08}


def distribute_pool(pool_micro: int, fee_bps: int) -> dict[int, int]:
    fee = pool_micro * fee_bps // 10_000
    distributable = pool_micro - fee
    out: dict[int, int] = {}
    allocated = 0
    for place, pct in REWARD_SPLITS.items():
        amount = int(distributable * pct)
        out[place] = amount
        allocated += amount
    # Dust to 1st
    out[1] += distributable - allocated
    return out