"""Arena64 MCP Server — expose tournament tools to AI assistants."""

from __future__ import annotations

import json
import os
from typing import Any

import httpx

API_URL = os.getenv("ARENA64_API_URL", "http://localhost:8000")
SERVICE_KEY = os.getenv("SERVICE_API_KEY", "arena64-dev-service-key")
USER_TOKEN = os.getenv("ARENA64_USER_TOKEN", "")


def _headers() -> dict[str, str]:
    h = {"X-Service-Key": SERVICE_KEY, "Content-Type": "application/json"}
    if USER_TOKEN:
        h["Authorization"] = f"Bearer {USER_TOKEN}"
    return h


async def _get(path: str, params: dict | None = None) -> Any:
    async with httpx.AsyncClient(base_url=API_URL, timeout=30) as client:
        r = await client.get(path, params=params, headers=_headers())
        r.raise_for_status()
        return r.json()


async def _post(path: str, body: dict | None = None, timeout: float = 30) -> Any:
    async with httpx.AsyncClient(base_url=API_URL, timeout=timeout) as client:
        r = await client.post(path, json=body or {}, headers=_headers())
        r.raise_for_status()
        return r.json()


TOOLS = [
    {
        "name": "listTournaments",
        "description": "List public Arena64 tournaments",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "getTournament",
        "description": "Get tournament details by id",
        "inputSchema": {
            "type": "object",
            "properties": {"tournament_id": {"type": "string"}},
            "required": ["tournament_id"],
        },
    },
    {
        "name": "joinTournament",
        "description": "Join a tournament (requires user token)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "tournament_id": {"type": "string"},
                "invite_code": {"type": "string"},
            },
            "required": ["tournament_id"],
        },
    },
    {
        "name": "buyCoachCredits",
        "description": "Purchase a coach credit pack (starter|pro|champion)",
        "inputSchema": {
            "type": "object",
            "properties": {"pack": {"type": "string"}},
            "required": ["pack"],
        },
    },
    {
        "name": "getBracket",
        "description": "Get World Cup–inspired bracket for a tournament",
        "inputSchema": {
            "type": "object",
            "properties": {"tournament_id": {"type": "string"}},
            "required": ["tournament_id"],
        },
    },
    {
        "name": "getCurrentChallenge",
        "description": "Get the current challenge/question for an active round",
        "inputSchema": {
            "type": "object",
            "properties": {"round_id": {"type": "string"}},
            "required": ["round_id"],
        },
    },
    {
        "name": "leaderboard",
        "description": "Get tournament leaderboard",
        "inputSchema": {
            "type": "object",
            "properties": {"tournament_id": {"type": "string"}},
            "required": ["tournament_id"],
        },
    },
    {
        "name": "submitAnswer",
        "description": "Submit an answer for the active challenge",
        "inputSchema": {
            "type": "object",
            "properties": {
                "round_id": {"type": "string"},
                "question_id": {"type": "string"},
                "option_id": {"type": "string"},
                "remaining_seconds": {"type": "number"},
                "nonce": {"type": "string"},
            },
            "required": ["round_id", "question_id", "nonce"],
        },
    },
    {
        "name": "nextRound",
        "description": "Advance to next question (admin)",
        "inputSchema": {
            "type": "object",
            "properties": {"round_id": {"type": "string"}},
            "required": ["round_id"],
        },
    },
    {
        "name": "claimReward",
        "description": "Claim a tournament reward into internal USDC balance",
        "inputSchema": {
            "type": "object",
            "properties": {"reward_id": {"type": "string"}},
            "required": ["reward_id"],
        },
    },
    {
        "name": "playerStats",
        "description": "Get current player profile stats",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "fairPlayScore",
        "description": "Get fair play score for current player",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "tournamentHistory",
        "description": "Premium player analysis / history (x402-aware)",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "runWebScout",
        "description": "DuckDuckGo search + scrape football sites + Ollama/Qwen fact extraction (Voya LLM pattern); store knowledge + questions",
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string"},
                "queries": {"type": "array", "items": {"type": "string"}},
                "urls": {"type": "array", "items": {"type": "string"}},
                "auto_approve": {"type": "boolean"},
            },
        },
    },
    {
        "name": "runWorldCupMonitor",
        "description": "Force one World Cup Monitor pass: search internet → update live WC 2026 snapshot + knowledge bank",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "getWorldCupMonitorStatus",
        "description": "Status of the continuous World Cup internet monitor agent",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "listScoutJobs",
        "description": "List recent Web Scout scrape jobs",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "listKnowledge",
        "description": "List recent knowledge facts scraped by Web Scout",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "getAgent",
        "description": "Get the coach's agent (requires user token) or agent by id",
        "inputSchema": {
            "type": "object",
            "properties": {"agent_id": {"type": "string"}},
        },
    },
    {
        "name": "getStrategy",
        "description": "Get strategy profile for the current coach's agent",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "listDecisionLogs",
        "description": "List agent decision logs for a match (spectator explainability)",
        "inputSchema": {
            "type": "object",
            "properties": {"match_id": {"type": "string"}},
            "required": ["match_id"],
        },
    },
    {
        "name": "researchKnowledge",
        "description": "Research shared football knowledge bank (competitor MCP help)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "number"},
            },
        },
    },
    {
        "name": "researchByCategory",
        "description": "Category-scoped research (PLAYER_ID, STADIUM, FOOTBALL, …)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "category": {"type": "string"},
                "limit": {"type": "number"},
            },
            "required": ["category"],
        },
    },
    {
        "name": "buyPremiumInsight",
        "description": "Alias for premiumInsight — x402 premium spend",
        "inputSchema": {
            "type": "object",
            "properties": {"payment_proof": {"type": "string"}},
        },
    },
    {
        "name": "getStandings",
        "description": "Tournament leaderboard / standings (read-only)",
        "inputSchema": {
            "type": "object",
            "properties": {"tournament_id": {"type": "string"}},
            "required": ["tournament_id"],
        },
    },
    {
        "name": "premiumInsight",
        "description": "Buy x402 premium insight for current user (agent resource spend)",
        "inputSchema": {
            "type": "object",
            "properties": {"payment_proof": {"type": "string"}},
        },
    },
]


async def call_tool(name: str, arguments: dict) -> Any:
    if name == "listTournaments":
        return await _get("/api/tournaments")
    if name == "getTournament":
        return await _get(f"/api/tournaments/{arguments['tournament_id']}")
    if name == "joinTournament":
        return await _post(
            f"/api/tournaments/{arguments['tournament_id']}/join",
            {"invite_code": arguments.get("invite_code")},
        )
    if name == "buyCoachCredits":
        return await _post("/api/coach/packs/purchase", {"pack": arguments["pack"]})
    if name == "getBracket":
        return await _get(f"/api/tournaments/{arguments['tournament_id']}/bracket")
    if name == "getCurrentChallenge":
        return await _get(f"/api/rounds/{arguments['round_id']}/current")
    if name == "leaderboard":
        return await _get(f"/api/tournaments/{arguments['tournament_id']}/leaderboard")
    if name == "submitAnswer":
        return await _post("/api/answers", arguments)
    if name == "nextRound":
        return await _post(f"/api/rounds/{arguments['round_id']}/next")
    if name == "claimReward":
        return await _post(f"/api/tournaments/rewards/{arguments['reward_id']}/claim")
    if name == "playerStats":
        return await _get("/api/users/me")
    if name == "fairPlayScore":
        me = await _get("/api/users/me")
        return {"fair_play_score": me.get("fair_play_score")}
    if name == "tournamentHistory":
        return await _get("/api/player/analysis")
    if name == "runWebScout":
        body = {
            "topic": arguments.get("topic") or "world-cup",
            "urls": arguments.get("urls"),
            "queries": arguments.get("queries"),
            "auto_approve": arguments.get("auto_approve"),
        }
        return await _post("/api/admin/scout/run", body, timeout=180)
    if name == "runWorldCupMonitor":
        return await _post("/api/admin/world-cup-monitor/run", {}, timeout=180)
    if name == "getWorldCupMonitorStatus":
        return await _get("/api/world-cup/monitor")
    if name == "listScoutJobs":
        return await _get("/api/admin/scout/jobs")
    if name == "listKnowledge":
        return await _get("/api/admin/scout/knowledge")
    if name == "getAgent":
        aid = arguments.get("agent_id")
        if aid:
            return await _get(f"/api/agents/{aid}")
        return await _get("/api/agents/me")
    if name == "getStrategy":
        agent = await _get("/api/agents/me")
        return agent.get("strategy") or {}
    if name == "listDecisionLogs":
        return await _get(f"/api/agents/matches/{arguments['match_id']}/decisions")
    if name == "researchKnowledge":
        params = {}
        if arguments.get("query"):
            params["q"] = arguments["query"]
        if arguments.get("limit"):
            params["limit"] = int(arguments["limit"])
        try:
            return await _get("/api/runtime/research", params)
        except Exception:
            return await _get("/api/admin/scout/knowledge")
    if name == "researchByCategory":
        params = {"category": arguments.get("category") or "FOOTBALL"}
        if arguments.get("query"):
            params["q"] = arguments["query"]
        if arguments.get("limit"):
            params["limit"] = int(arguments["limit"])
        return await _get("/api/runtime/research", params)
    if name == "buyPremiumInsight" or name == "premiumInsight":
        headers = _headers()
        if arguments.get("payment_proof"):
            headers["X-PAYMENT"] = arguments["payment_proof"]
        async with httpx.AsyncClient(base_url=API_URL, timeout=30) as client:
            r = await client.get("/api/player/analysis", headers=headers)
            r.raise_for_status()
            return r.json()
    if name == "getStandings":
        return await _get(f"/api/tournaments/{arguments['tournament_id']}/leaderboard")
    raise ValueError(f"Unknown tool: {name}")


def main() -> None:
    """Minimal stdio JSON-RPC loop compatible with MCP-style tool listing."""
    import sys

    print(json.dumps({"jsonrpc": "2.0", "method": "ready", "params": {"tools": [t["name"] for t in TOOLS]}}), flush=True)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            method = req.get("method")
            req_id = req.get("id")
            if method == "tools/list":
                print(json.dumps({"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}}), flush=True)
            elif method == "tools/call":
                import asyncio

                params = req.get("params", {})
                result = asyncio.run(call_tool(params["name"], params.get("arguments") or {}))
                print(
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": req_id,
                            "result": {"content": [{"type": "text", "text": json.dumps(result)}]},
                        }
                    ),
                    flush=True,
                )
            else:
                print(json.dumps({"jsonrpc": "2.0", "id": req_id, "error": {"message": "unknown method"}}), flush=True)
        except Exception as exc:  # noqa: BLE001
            print(json.dumps({"jsonrpc": "2.0", "error": {"message": str(exc)}}), flush=True)


if __name__ == "__main__":
    main()