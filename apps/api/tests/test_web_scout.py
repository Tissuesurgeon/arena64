from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.web_scout import WebScoutAgent


def test_extract_facts_finds_world_cup_lines():
    agent = WebScoutAgent()
    text = """
    The 2018 FIFA World Cup was won by France.
    In 2022 Argentina won the FIFA World Cup after a dramatic final.
    Unrelated line without enough context.
    """
    facts = agent.extract_facts("Test", text, "https://www.espn.com/soccer/story/_/id/1")
    assert len(facts) >= 1
    assert any("2018" in f["fact"] or "2022" in f["fact"] for f in facts)


def test_fact_to_questions_champion():
    agent = WebScoutAgent()
    entry = SimpleNamespace(
        source_url="https://www.bbc.com/sport/football/world-cup",
        title="World Cup",
        category="champions",
        fact="In 2018, France won the FIFA World Cup.",
        entities=["2018", "France"],
        confidence=0.8,
    )
    qs = agent.fact_to_questions(entry)
    assert len(qs) >= 1
    assert any(q["challenge_type"] == "FOOTBALL" for q in qs)
    assert any(opt["is_correct"] and "France" in opt["label"] for q in qs for opt in q["options"])


def test_host_allowlist_football_not_wikipedia():
    agent = WebScoutAgent()
    assert agent._host_allowed("https://www.espn.com/soccer/story")
    assert agent._host_allowed("https://www.fifa.com/tournaments/mens/worldcup")
    assert not agent._host_allowed("https://en.wikipedia.org/wiki/FIFA_World_Cup")


@pytest.mark.asyncio
async def test_discover_urls_uses_fallback_when_search_empty():
    agent = WebScoutAgent()
    client = MagicMock()
    agent.search_web = AsyncMock(return_value=[])
    urls, meta = await agent.discover_urls(client, "world-cup", queries=["FIFA World Cup"], max_urls=5)
    assert urls
    assert all("wikipedia" not in u for u in urls)
    assert meta["search_engine"] == "fallback_seeds"
    assert meta["paid_apis"] is False


@pytest.mark.asyncio
async def test_llm_enrich_uses_chat_with_fallback():
    agent = WebScoutAgent()

    async def fake_chat(**kwargs):
        assert kwargs.get("json_mode") is True
        return (
            '{"facts":[{"fact":"France won the 2018 FIFA World Cup in Russia.","category":"champions","entities":["2018","France"]}]}',
            "ollama",
        )

    with patch("app.agents.web_scout.chat_with_fallback", fake_chat):
        facts = await agent.llm_enrich_facts("t", "article about France 2018", "https://www.espn.com/x")

    assert len(facts) == 1
    assert "France" in facts[0]["fact"]
    assert facts[0]["llm_provider"] == "ollama"
    assert agent._last_llm_provider == "ollama"


@pytest.mark.asyncio
async def test_llm_enrich_empty_when_no_provider():
    agent = WebScoutAgent()

    async def none_chat(**kwargs):
        return None

    with patch("app.agents.web_scout.chat_with_fallback", none_chat):
        facts = await agent.llm_enrich_facts("t", "text", "https://www.espn.com/x")
    assert facts == []
