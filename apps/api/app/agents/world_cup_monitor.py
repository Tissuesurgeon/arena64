"""World Cup Monitor — continuous web watch that refreshes the live 2026 snapshot + knowledge bank."""

from __future__ import annotations

import json
import logging
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from app.agents.web_scout import USER_AGENT, web_scout_agent
from app.core.config import get_settings
from app.integrations.llm import chat_with_fallback

logger = logging.getLogger(__name__)

_DATA = Path(__file__).resolve().parent.parent / "data"
_BASE_SNAPSHOT = _DATA / "world_cup_2026.json"
_LIVE_SNAPSHOT = _DATA / "world_cup_2026_live.json"
_STATUS_PATH = _DATA / "world_cup_monitor_status.json"

MONITOR_QUERIES = [
    "FIFA World Cup 2026 latest results today",
    "World Cup 2026 score latest news",
    "FIFA World Cup 2026 Golden Boot standings live",
    "World Cup 2026 upcoming matches fixtures",
    "FIFA World Cup 2026 semi-final final update",
    "World Cup 2026 tournament stage headlines",
]

SNAPSHOT_SYSTEM = """You are Arena64 World Cup Monitor.
Extract ONLY verifiable FIFA World Cup 2026 updates from the articles.
Return JSON with this shape (omit unknown fields rather than inventing):
{
  "stage": "string stage name",
  "stage_code": "GROUP|R32|R16|QF|SF|FINAL|COMPLETE",
  "headline": "one sentence current headline",
  "updated_at": "YYYY-MM-DD",
  "recent_results": [{"round":"","date":"YYYY-MM-DD","fixture":"Team A 1–0 Team B","venue":""}],
  "upcoming": [{"round":"","date":"YYYY-MM-DD","fixture":"Team A vs Team B","venue":""}],
  "golden_boot": [{"rank":1,"player":"","team":"","goals":0,"assists":0}],
  "tournament_so_far": {
    "story": "short paragraph",
    "highlights": ["..."],
    "surviving": ["Team", "..."],
    "by_the_numbers": [{"label":"","value":""}]
  },
  "fun_facts": [{"id":"slug","title":"","fact":"","tags":["live","2026"]}],
  "knowledge_facts": [{"title":"","fact":""}]
}
Rules: no Wikipedia; no invented scores; keep arrays short (max 8 items each).
"""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_base_snapshot() -> dict[str, Any]:
    if not _BASE_SNAPSHOT.is_file():
        return {}
    return json.loads(_BASE_SNAPSHOT.read_text(encoding="utf-8"))


def load_live_snapshot() -> dict[str, Any] | None:
    if not _LIVE_SNAPSHOT.is_file():
        return None
    try:
        return json.loads(_LIVE_SNAPSHOT.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def load_effective_snapshot() -> dict[str, Any]:
    base = load_base_snapshot()
    live = load_live_snapshot()
    if not live:
        return base
    merged = deepcopy(base)
    for key, value in live.items():
        if key in ("_monitor", "disclaimer"):
            continue
        if value is None or value == "" or value == [] or value == {}:
            continue
        merged[key] = value
    # Prefer live monitor metadata
    if live.get("updated_at"):
        merged["updated_at"] = live["updated_at"]
    if live.get("_monitor"):
        merged["_monitor"] = live["_monitor"]
    return merged


def read_monitor_status() -> dict[str, Any]:
    if _STATUS_PATH.is_file():
        try:
            return json.loads(_STATUS_PATH.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
    return {
        "enabled": True,
        "running": False,
        "last_run_at": None,
        "last_status": "never",
        "last_error": None,
        "facts_stored": 0,
        "snapshot_updated": False,
    }


def _write_status(payload: dict[str, Any]) -> None:
    _STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _STATUS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _deep_merge_list_by_key(existing: list, incoming: list, key: str) -> list:
    if not incoming:
        return existing
    if not existing:
        return incoming
    by_key: dict[str, Any] = {}
    for item in existing:
        if isinstance(item, dict) and item.get(key):
            by_key[str(item[key])] = item
    for item in incoming:
        if not isinstance(item, dict):
            continue
        k = item.get(key)
        if k:
            by_key[str(k)] = {**(by_key.get(str(k)) or {}), **item}
        else:
            existing.append(item)
    # Preserve order: incoming first for freshness, then remaining existing
    out: list = []
    seen: set[str] = set()
    for item in incoming:
        if isinstance(item, dict) and item.get(key):
            kk = str(item[key])
            out.append(by_key[kk])
            seen.add(kk)
    for item in existing:
        if isinstance(item, dict) and item.get(key):
            kk = str(item[key])
            if kk not in seen:
                out.append(item)
                seen.add(kk)
        elif item not in out:
            out.append(item)
    return out[:12]


def merge_snapshot_patch(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(base)
    scalar_keys = ("stage", "stage_code", "headline", "updated_at", "final_date", "final_venue")
    for key in scalar_keys:
        val = patch.get(key)
        if isinstance(val, str) and val.strip():
            out[key] = val.strip()

    if isinstance(patch.get("recent_results"), list) and patch["recent_results"]:
        out["recent_results"] = patch["recent_results"][:8]
    if isinstance(patch.get("upcoming"), list) and patch["upcoming"]:
        out["upcoming"] = patch["upcoming"][:8]
    if isinstance(patch.get("golden_boot"), list) and patch["golden_boot"]:
        out["golden_boot"] = patch["golden_boot"][:10]

    tsf = patch.get("tournament_so_far")
    if isinstance(tsf, dict) and tsf:
        cur = dict(out.get("tournament_so_far") or {})
        if tsf.get("story"):
            cur["story"] = str(tsf["story"]).strip()
        if isinstance(tsf.get("highlights"), list) and tsf["highlights"]:
            cur["highlights"] = [str(h).strip() for h in tsf["highlights"] if str(h).strip()][:12]
        if isinstance(tsf.get("surviving"), list) and tsf["surviving"]:
            cur["surviving"] = [str(s).strip() for s in tsf["surviving"] if str(s).strip()][:16]
        if isinstance(tsf.get("by_the_numbers"), list) and tsf["by_the_numbers"]:
            cur["by_the_numbers"] = tsf["by_the_numbers"][:8]
        out["tournament_so_far"] = cur

    if isinstance(patch.get("fun_facts"), list) and patch["fun_facts"]:
        existing = list(out.get("fun_facts") or [])
        out["fun_facts"] = _deep_merge_list_by_key(existing, patch["fun_facts"], "id")[:24]

    return out


class WorldCupMonitorAgent:
    """Continuously monitors football news and updates the World Cup 2026 live snapshot."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._query_index = 0

    def _next_queries(self, n: int = 3) -> list[str]:
        out: list[str] = []
        for _ in range(n):
            out.append(MONITOR_QUERIES[self._query_index % len(MONITOR_QUERIES)])
            self._query_index += 1
        return out

    async def _extract_snapshot_patch(self, articles: list[dict[str, str]]) -> dict[str, Any]:
        if not articles:
            return {}
        blob_parts = []
        for a in articles[:5]:
            blob_parts.append(
                f"### {a.get('title') or 'Article'}\nURL: {a.get('url')}\n{a.get('text', '')[:3500]}"
            )
        user = (
            "Update FIFA World Cup 2026 live data from these articles.\n\n"
            + "\n\n".join(blob_parts)
            + "\n\nRespond with JSON only."
        )
        result = await chat_with_fallback(
            system=SNAPSHOT_SYSTEM,
            user=user,
            json_mode=True,
            temperature=0.1,
            max_tokens=2048,
        )
        if not result:
            return {}
        content, provider = result
        try:
            start, end = content.find("{"), content.rfind("}")
            if start == -1 or end <= start:
                return {}
            data = json.loads(content[start : end + 1])
            if not isinstance(data, dict):
                return {}
            data["_llm_provider"] = provider
            return data
        except Exception:  # noqa: BLE001
            logger.warning("World Cup monitor LLM JSON parse failed")
            return {}

    async def run_once(self, db, *, auto_approve: bool | None = None) -> dict[str, Any]:
        from app.models import ScrapeJob

        settings = get_settings()
        approve = settings.scout_auto_approve if auto_approve is None else auto_approve
        started = _utc_now_iso()
        status = {
            **read_monitor_status(),
            "running": True,
            "last_run_at": started,
            "last_status": "running",
            "last_error": None,
        }
        _write_status(status)

        queries = self._next_queries(3)
        pages_scraped = 0
        facts_stored = 0
        questions_created = 0
        snapshot_updated = False
        sources: list[str] = []
        search_meta: dict[str, Any] = {}

        job = ScrapeJob(
            status="running",
            topic="world-cup-2026",
            urls=[],
            meta={"agent": "world_cup_monitor", "queries": queries},
        )
        db.add(job)
        await db.flush()
        job_id = job.id

        try:
            async with httpx.AsyncClient(
                timeout=45,
                headers={"User-Agent": USER_AGENT, "Accept-Language": "en"},
            ) as client:
                urls, search_meta = await web_scout_agent.discover_urls(
                    client, "world-cup-2026", queries=queries
                )
                job.urls = urls
                articles: list[dict[str, str]] = []
                for url in urls[:6]:
                    try:
                        title, text = await web_scout_agent.fetch_page(client, url)
                    except Exception as exc:  # noqa: BLE001
                        logger.debug("monitor fetch failed %s: %s", url, exc)
                        continue
                    pages_scraped += 1
                    sources.append(url)
                    articles.append({"title": title, "url": url, "text": text})

                    extracted = web_scout_agent.extract_facts(title, text, url)
                    enriched = await web_scout_agent.llm_enrich_facts(title, text, url)
                    combined = enriched if enriched else extracted
                    if enriched and extracted:
                        seen = {f["fact"].lower() for f in enriched}
                        for f in extracted:
                            if f["fact"].lower() not in seen:
                                combined.append(f)
                    for payload in combined[:8]:
                        entry = await web_scout_agent.store_fact(
                            db, job_id, payload, topic="world-cup-2026"
                        )
                        if entry is None:
                            continue
                        facts_stored += 1
                        questions_created += await web_scout_agent.store_questions_from_entry(
                            db, entry, approve
                        )

            patch = await self._extract_snapshot_patch(articles)
            knowledge_extra = patch.pop("knowledge_facts", None) if isinstance(patch, dict) else None
            provider = patch.pop("_llm_provider", None) if isinstance(patch, dict) else None

            if isinstance(knowledge_extra, list):
                for item in knowledge_extra[:6]:
                    if not isinstance(item, dict):
                        continue
                    fact = str(item.get("fact") or "").strip()
                    if len(fact) < 20:
                        continue
                    entry = await web_scout_agent.store_fact(
                        db,
                        job_id,
                        {
                            "fact": fact,
                            "title": str(item.get("title") or "World Cup live update")[:200],
                            "category": "world-cup-2026",
                            "source_url": sources[0] if sources else "",
                            "confidence": 0.85,
                        },
                        topic="world-cup-2026",
                    )
                    if entry:
                        facts_stored += 1

            base = load_effective_snapshot() or load_base_snapshot()
            if patch:
                if not patch.get("updated_at"):
                    patch["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                merged = merge_snapshot_patch(base, patch)
                merged["_monitor"] = {
                    "agent": "world_cup_monitor",
                    "updated_at": _utc_now_iso(),
                    "sources": sources[:8],
                    "queries": queries,
                    "llm_provider": provider,
                    "search": search_meta,
                    "job_id": job_id,
                }
                _LIVE_SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
                _LIVE_SNAPSHOT.write_text(json.dumps(merged, indent=2), encoding="utf-8")
                snapshot_updated = True

            job.pages_scraped = pages_scraped
            job.facts_stored = facts_stored
            job.questions_created = questions_created
            job.status = "completed"
            job.finished_at = datetime.utcnow()
            job.meta = {
                **(job.meta or {}),
                **search_meta,
                "snapshot_updated": snapshot_updated,
                "llm_provider": provider,
            }

            result = {
                "ok": True,
                "job_id": job_id,
                "pages_scraped": pages_scraped,
                "facts_stored": facts_stored,
                "questions_created": questions_created,
                "snapshot_updated": snapshot_updated,
                "sources": sources,
                "queries": queries,
                "llm_provider": provider,
            }
            _write_status(
                {
                    "enabled": True,
                    "running": False,
                    "last_run_at": started,
                    "finished_at": _utc_now_iso(),
                    "last_status": "ok",
                    "last_error": None,
                    "facts_stored": facts_stored,
                    "questions_created": questions_created,
                    "pages_scraped": pages_scraped,
                    "snapshot_updated": snapshot_updated,
                    "sources": sources[:8],
                    "queries": queries,
                    "job_id": job_id,
                }
            )
            await db.flush()
            return result
        except Exception as exc:  # noqa: BLE001
            logger.exception("World Cup monitor run failed")
            job.status = "failed"
            job.error = str(exc)[:1000]
            job.finished_at = datetime.utcnow()
            job.pages_scraped = pages_scraped
            job.facts_stored = facts_stored
            job.questions_created = questions_created
            _write_status(
                {
                    "enabled": True,
                    "running": False,
                    "last_run_at": started,
                    "finished_at": _utc_now_iso(),
                    "last_status": "error",
                    "last_error": str(exc)[:500],
                    "facts_stored": facts_stored,
                    "snapshot_updated": snapshot_updated,
                    "job_id": job_id,
                }
            )
            await db.flush()
            raise


world_cup_monitor_agent = WorldCupMonitorAgent()
