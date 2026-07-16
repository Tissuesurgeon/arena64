"""Integration-style tournament simulation without DB (pure engine math)."""

from app.services.scoring import distribute_pool, score_answer


def test_simulated_match_scoring():
    # Player A answers 5 correct with 8s left each; B gets 3 correct with 12s
    score_a = sum(score_answer(True, 8) for _ in range(5))
    score_b = sum(score_answer(True, 12) for _ in range(3))
    assert score_a == 5 * (100 + 16)
    assert score_b == 3 * (100 + 24)
    assert score_a > score_b


def test_pool_with_fee():
    splits = distribute_pool(10_000_000, 500)  # 5% fee
    assert sum(splits.values()) == 9_500_000
