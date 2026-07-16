import importlib.util
from pathlib import Path

from app.services.scoring import compare_tiebreak, distribute_pool, score_answer


def test_score_correct():
    assert score_answer(True, 10) == 120
    assert score_answer(True, 0) == 100
    assert score_answer(False, 10) == 0


def test_reward_splits():
    splits = distribute_pool(1_000_000, 0)
    assert sum(splits.values()) == 1_000_000
    assert splits[1] >= splits[2] >= splits[3] >= splits[4]


def test_tiebreak_fair_play():
    assert compare_tiebreak(99, 100, 5, 90, 100, 5) == 1
    assert compare_tiebreak(90, 100, 5, 99, 100, 5) == -1


def test_app_module_path():
    main = Path(__file__).resolve().parents[1] / "app" / "main.py"
    assert main.exists()
    assert importlib.util.find_spec("app.services.scoring") is not None
