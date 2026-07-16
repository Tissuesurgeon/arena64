# Arena64 Web Scout Skill

## When to use
Gather World Cup / football knowledge via free web search + LLM fact extraction (Voya-style), then store facts and quiz questions in Arena64's database.

## Do not use
- Paid search APIs (Google CSE) or paid football data APIs
- Wikipedia / Wikimedia
- Hosts outside `SCOUT_ALLOWED_HOSTS`

## How it works (Voya LLM pattern)
1. **DuckDuckGo HTML** search (no API key) biased toward ESPN, BBC, Goal, FIFA, Sky, Transfermarkt, etc.
2. Scrape discovered pages.
3. Fact extraction via `chat_with_fallback()`:
   - **Ollama** local first (`OLLAMA_MODEL=qwen2.5`) when enabled/reachable
   - then **Qwen** cloud (DashScope / Model Studio OpenAI-compatible) when `QWEN_API_KEY` is set
   - then **heuristics** if both LLMs fail
4. Store `knowledge_entries` → generate FOOTBALL/MEMORY `questions`.

## Setup (local / free)
```bash
ollama pull qwen2.5
# AI_PROVIDER=auto
# OLLAMA_ENABLED=true
# OLLAMA_MODEL=qwen2.5
```

## Optional cloud Qwen
```bash
QWEN_API_KEY=sk-...
# or DASHSCOPE_API_KEY=...
QWEN_CHAT_MODEL=qwen-plus
AI_PROVIDER=auto   # or qwen
```

## Code map (mirrors Voya)
- `app/integrations/ollama/client.py` — local httpx `/api/chat`
- `app/integrations/qwen/client.py` — `AsyncOpenAI` DashScope compatible-mode
- `app/integrations/llm.py` — `chat_with_fallback()`
- `app/prompts/web_scout.system.md` — system prompt

## Instructions
1. Call `POST /api/admin/scout/run` (admin JWT) or MCP `runWebScout`.
2. Optional body: `{ "topic": "world-cup", "queries": ["..."], "urls": ["https://..."] }`.
