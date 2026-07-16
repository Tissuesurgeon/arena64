"""Arena64 Competition Runtime — OpenClaw-style poll loop (engines + skills)."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from pathlib import Path
from typing import Any

import httpx

from agent_package import from_live_work_player
from engines.decision import DecisionEngine, decision_engine
from engines.experience import ExperienceRecorder
from engines.memory import memory_engine
from engines.strategy import strategy_engine
from skills.registry import skills_registry
from skills.research import skill_name_for_category
from skills.tool_registry import tool_registry

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("arena64-ai-runtime")

API_URL = os.getenv("ARENA64_API_URL", "http://127.0.0.1:8000")
SERVICE_KEY = os.getenv("SERVICE_API_KEY", "arena64-dev-service-key")
POLL_SECONDS = float(os.getenv("RUNTIME_POLL_SECONDS", "2.5"))
WORKER_ID = os.getenv("RUNTIME_WORKER_ID", "0")
MAX_PARALLEL = int(os.getenv("RUNTIME_MAX_PARALLEL", "16"))


def _load_competitor_system() -> str:
    candidates = [
        Path(__file__).resolve().parents[2] / "packages" / "prompts" / "competitor.system.md",
        Path("/agent-prompts/competitor.system.md"),
    ]
    for path in candidates:
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            if "COMPETITOR_SYSTEM" in text and '"""' in text:
                start = text.find('"""', text.find("COMPETITOR_SYSTEM")) + 3
                end = text.find('"""', start)
                if start > 2 and end > start:
                    return text[start:end].strip()
            return text.strip()
    skill = skills_registry.competitor_prompt()
    return skill or DecisionEngine().system_prompt


# Inject competitor skill + system prompt into decision engine
_system = _load_competitor_system()
_extra = skills_registry.competitor_prompt()
if _extra and _extra not in _system:
    _system = f"{_system}\n\n# Competitor skill\n{_extra[:2000]}"
decision_engine.system_prompt = _system

experience = ExperienceRecorder(API_URL, SERVICE_KEY)


def _svc_headers() -> dict[str, str]:
    return {"Content-Type": "application/json", "X-Service-Key": SERVICE_KEY}


def _auth_headers(token: str) -> dict[str, str]:
    return {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}


async def run_decision_pipeline(
    client: httpx.AsyncClient,
    *,
    pkg,
    question: dict,
) -> dict:
    """
    Strategy → Memory → Decision → (optional Skills) → Re-decide.
    Max ~5–8 steps.
    """
    policy = strategy_engine.evaluate(
        agent_id=pkg.id,
        tournament_id=pkg.tournament_id,
        strategy=pkg.strategy,
        is_system_agent=pkg.is_system_agent,
    )
    memory_ctx = memory_engine.context_for_decision(pkg.memory)
    cat_skill = skill_name_for_category(str(question.get("challenge_type") or ""))
    skill_prompt = skills_registry.prompt_for(cat_skill)

    decision = await decision_engine.initial(
        question=question,
        strategy=pkg.strategy,
        memory_ctx=memory_ctx,
        policy=policy,
        skill_prompt=skill_prompt,
    )

    if policy.accelerated:
        decision["want_mcp"] = False
        decision["want_premium"] = False
        decision["want_coach"] = False
        return decision

    prefer = memory_engine.should_prefer_research(
        pkg.memory, str(question.get("challenge_type") or "")
    )
    if decision_engine.needs_help(decision, policy) or (prefer and policy.allow_mcp):
        tool_results = await tool_registry.run_skill_plan(
            client,
            question=question,
            token=pkg.token,
            agent_id=pkg.id,
            tournament_id=pkg.tournament_id,
            policy=policy,
            prefer_research=prefer or decision_engine.needs_help(decision, policy),
            budget=pkg.budget,
        )
        if tool_results:
            # Apply coach remove_two to option set if present
            for tr in tool_results:
                if tr.get("tool") == "coachRemoveTwo":
                    removed = set(tr.get("remove_option_ids") or [])
                    if removed and decision.get("option_id") in removed:
                        opts = [o for o in (question.get("options") or []) if o["id"] not in removed]
                        if opts:
                            decision["option_id"] = opts[0]["id"]
            decision = await decision_engine.redecide(
                question=question,
                strategy=pkg.strategy,
                memory_ctx=memory_ctx,
                prior=decision,
                tool_results=tool_results,
                policy=policy,
            )

    skills = decision.get("skills_used") or []
    decision["want_mcp"] = any(s.startswith("research") for s in skills)
    decision["want_premium"] = "buyPremiumInsight" in skills
    decision["want_coach"] = "coachRemoveTwo" in skills
    return decision


async def process_player(
    client: httpx.AsyncClient,
    match: dict,
    round_id: str,
    player: dict,
) -> None:
    pkg = from_live_work_player(player, match)
    if not pkg or not pkg.token:
        return
    try:
        cur = await client.get(
            f"{API_URL}/api/rounds/{round_id}/current",
            headers=_auth_headers(pkg.token),
            timeout=60,
        )
        if cur.status_code >= 400:
            return
        data = cur.json()
    except Exception:
        return
    if data.get("done") or data.get("user_answered"):
        return
    q = data.get("question") or {}
    if not q:
        return

    policy = strategy_engine.evaluate(
        agent_id=pkg.id,
        tournament_id=pkg.tournament_id,
        strategy=pkg.strategy,
        is_system_agent=pkg.is_system_agent,
    )
    await asyncio.sleep(policy.thinking_ms / 1000.0)

    t0 = time.time()
    decision = await run_decision_pipeline(client, pkg=pkg, question=q)
    latency = int((time.time() - t0) * 1000)

    is_correct: bool | None = None
    try:
        ans = await client.post(
            f"{API_URL}/api/answers",
            headers=_auth_headers(pkg.token),
            json={
                "round_id": round_id,
                "question_id": q["id"],
                "option_id": decision.get("option_id"),
                "remaining_seconds": max(0, 20 - latency / 1000),
                "nonce": data.get("nonce"),
            },
            timeout=60,
        )
        if ans.status_code < 400:
            body = ans.json()
            if "correct" in body:
                is_correct = bool(body["correct"])
    except Exception as exc:  # noqa: BLE001
        logger.debug("answer: %s", exc)
        return

    await experience.record(
        client,
        agent_id=pkg.id,
        match_id=match["id"],
        round_id=round_id,
        question_id=q["id"],
        decision=decision,
        latency_ms=latency + policy.thinking_ms,
        accelerated=policy.accelerated,
        is_correct=is_correct,
    )


async def tick(client: httpx.AsyncClient) -> None:
    r = await client.get(f"{API_URL}/api/runtime/live-work", headers=_svc_headers(), timeout=60)
    r.raise_for_status()
    payload = r.json()
    tasks: list[Any] = []

    for match in payload.get("matches") or []:
        worker_count = max(1, int(os.getenv("RUNTIME_WORKER_COUNT", "1")))
        wid = int(WORKER_ID) % worker_count
        mid = str(match.get("id") or "")
        if worker_count > 1 and mid and (hash(mid) % worker_count) != wid:
            continue

        round_id = match.get("round_id")
        if not round_id:
            try:
                started = await client.post(
                    f"{API_URL}/api/runtime/ensure-started/{match['id']}",
                    headers=_svc_headers(),
                    timeout=60,
                )
                if started.status_code < 400:
                    round_id = started.json().get("round_id")
            except Exception as exc:  # noqa: BLE001
                logger.debug("ensure-started: %s", exc)
                continue
        if not round_id:
            continue

        for player in match.get("players") or []:
            tasks.append(process_player(client, match, round_id, player))

    if not tasks:
        return
    for i in range(0, len(tasks), MAX_PARALLEL):
        batch = tasks[i : i + MAX_PARALLEL]
        await asyncio.gather(*batch, return_exceptions=True)


async def runtime_loop() -> None:
    logger.info(
        "Arena64 competition runtime worker=%s skills=%s → %s",
        WORKER_ID,
        skills_registry.all_names(),
        API_URL,
    )
    async with httpx.AsyncClient() as client:
        for _ in range(90):
            try:
                await client.get(f"{API_URL}/health", timeout=5)
                break
            except Exception:
                await asyncio.sleep(2)
        while True:
            try:
                await tick(client)
            except Exception as exc:  # noqa: BLE001
                logger.warning("tick error: %s", exc)
            await asyncio.sleep(POLL_SECONDS)


def main() -> None:
    asyncio.run(runtime_loop())


if __name__ == "__main__":
    main()
