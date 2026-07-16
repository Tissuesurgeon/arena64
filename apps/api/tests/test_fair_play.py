import pytest

from app.agents.fair_play import FairPlayAgent


def test_fair_play_flags_for_review():
    agent = FairPlayAgent()
    assert "focus_loss" in agent.PENALTIES
    assert "paste_attempt" in agent.PENALTIES
    assert agent.PENALTIES["paste_attempt"] >= agent.PENALTIES["focus_loss"]
