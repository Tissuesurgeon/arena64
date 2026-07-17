# Arena64 World Cup Monitor Skill

## When to use
Continuously watch the open internet for FIFA World Cup 2026 news, then refresh:
1. the **live tournament snapshot** (stage, headline, results, fixtures, Golden Boot)
2. the shared **knowledge bank** agents research mid-match

## Do not use
- Paid search or paid football data APIs
- Wikipedia / Wikimedia
- Hosts outside `SCOUT_ALLOWED_HOSTS`

## How it works
1. Every `WORLD_CUP_MONITOR_INTERVAL_MINUTES` (default **30**), the monitor wakes.
2. Free **DuckDuckGo** search for rotating live queries (results, Golden Boot, fixtures).
3. Scrape allowlisted football sites (FIFA, ESPN, BBC, Goal, Sky, …).
4. Extract facts into `knowledge_entries` (+ quiz questions) via the Web Scout pipeline.
5. Ask the LLM (`chat_with_fallback`: Ollama → Qwen → heuristics) for a **structured snapshot patch**.
6. Merge into `apps/api/app/data/world_cup_2026_live.json` (overlay on the bootstrap snapshot).
7. Public `/api/world-cup` serves the merged live view.

## Config
```bash
WORLD_CUP_MONITOR_ENABLED=true
WORLD_CUP_MONITOR_INTERVAL_MINUTES=15
# Reuses scout allowlist + LLM settings
SCOUT_ALLOWED_HOSTS=...
AI_PROVIDER=auto
OLLAMA_ENABLED=true
QWEN_API_KEY=...   # optional cloud fallback
```

## Manual trigger (admin)
```http
POST /api/admin/world-cup-monitor/run
GET  /api/admin/world-cup-monitor/status
GET  /api/world-cup/monitor
```

## Code map
- `apps/api/app/agents/world_cup_monitor.py` — agent
- `apps/api/app/services/world_cup_monitor_worker.py` — scheduler
- `apps/api/app/routers/world_cup.py` — live snapshot merge
- Sibling skill: `arena64-web-scout` (search/scrape primitives)
