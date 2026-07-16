"""Bootstrap World Cup history + current 2026 snapshot into knowledge_entries."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ChallengeType, KnowledgeEntry, Question, QuestionOption

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
HISTORY_PATH = DATA_DIR / "world_cup_history.json"
SNAPSHOT_2026_PATH = DATA_DIR / "world_cup_2026.json"
SOURCE_PREFIX_HISTORY = "arena64://bootstrap/world-cup/"
SOURCE_PREFIX_2026 = "arena64://bootstrap/world-cup-2026/"

DISTRACTORS = [
    "Brazil",
    "Germany",
    "Argentina",
    "France",
    "Italy",
    "Spain",
    "England",
    "Netherlands",
    "Uruguay",
    "Portugal",
]


def _load_history() -> list[dict]:
    if not HISTORY_PATH.exists():
        logger.warning("world_cup_history.json missing at %s", HISTORY_PATH)
        return []
    raw = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    return list(raw.get("tournaments") or [])


def _load_2026() -> dict:
    if not SNAPSHOT_2026_PATH.exists():
        logger.warning("world_cup_2026.json missing at %s", SNAPSHOT_2026_PATH)
        return {}
    return json.loads(SNAPSHOT_2026_PATH.read_text(encoding="utf-8"))


def _facts_from_2026(snap: dict) -> list[dict]:
    """Flatten current tournament JSON into knowledge rows (fun facts + structured data)."""
    rows: list[dict] = []
    updated = snap.get("updated_at") or "2026"

    for ff in snap.get("fun_facts") or []:
        fid = ff.get("id") or ff.get("title") or "fact"
        fact = (ff.get("fact") or "").strip()
        if not fact:
            continue
        rows.append(
            {
                "slug": f"fun-{fid}",
                "title": ff.get("title") or f"WC 2026 · {fid}",
                "fact": fact,
                "entities": list(ff.get("tags") or ["2026"]),
                "raw": ff,
            }
        )

    hosts = snap.get("hosts") or []
    if hosts:
        rows.append(
            {
                "slug": "hosts",
                "title": "World Cup 2026 hosts",
                "fact": (
                    f"FIFA World Cup 2026 is co-hosted by {', '.join(hosts)}. "
                    f"Current stage (as of {updated}): {snap.get('stage') or 'in progress'}."
                ),
                "entities": list(hosts) + ["2026"],
                "raw": {"hosts": hosts, "stage": snap.get("stage")},
            }
        )

    snapshot = snap.get("snapshot") or {}
    if snapshot.get("format"):
        rows.append(
            {
                "slug": "format",
                "title": "World Cup 2026 format",
                "fact": f"World Cup 2026 format: {snapshot['format']}.",
                "entities": ["2026", "format", "48"],
                "raw": snapshot,
            }
        )

    for i, row in enumerate(snap.get("golden_boot") or []):
        player = row.get("player")
        if not player:
            continue
        rows.append(
            {
                "slug": f"golden-boot-{i + 1}",
                "title": f"Golden Boot #{row.get('rank', i + 1)} · {player}",
                "fact": (
                    f"{player} ({row.get('team')}) has {row.get('goals')} goals "
                    f"and {row.get('assists', 0)} assists at World Cup 2026 "
                    f"(Golden Boot rank {row.get('rank', i + 1)} as of {updated})."
                ),
                "entities": [player, row.get("team"), "golden-boot", "2026"],
                "raw": row,
            }
        )

    for i, m in enumerate(snap.get("recent_results") or []):
        fixture = m.get("fixture")
        if not fixture:
            continue
        rows.append(
            {
                "slug": f"result-{i}",
                "title": f"{m.get('round') or 'Match'}: {fixture}",
                "fact": (
                    f"{m.get('round')} on {m.get('date')}: {fixture}"
                    f"{(' at ' + m['venue']) if m.get('venue') else ''} (World Cup 2026)."
                ),
                "entities": ["2026", m.get("round"), m.get("venue")],
                "raw": m,
            }
        )

    for i, m in enumerate(snap.get("upcoming") or []):
        fixture = m.get("fixture")
        if not fixture:
            continue
        rows.append(
            {
                "slug": f"upcoming-{i}",
                "title": f"Upcoming · {m.get('round') or 'Match'}",
                "fact": (
                    f"Upcoming World Cup 2026 {m.get('round')}: {fixture} on {m.get('date')}"
                    f"{(' at ' + m['venue']) if m.get('venue') else ''}."
                ),
                "entities": ["2026", m.get("round"), "upcoming"],
                "raw": m,
            }
        )

    so_far = snap.get("tournament_so_far") or {}
    if so_far.get("story"):
        rows.append(
            {
                "slug": "story",
                "title": "Tournament so far",
                "fact": so_far["story"],
                "entities": ["2026", "story"],
                "raw": so_far,
            }
        )
    for i, h in enumerate(so_far.get("highlights") or []):
        rows.append(
            {
                "slug": f"highlight-{i}",
                "title": f"2026 highlight {i + 1}",
                "fact": h if str(h).endswith(".") else f"{h}.",
                "entities": ["2026", "highlight"],
                "raw": {"highlight": h},
            }
        )
    for i, n in enumerate(so_far.get("by_the_numbers") or []):
        label = n.get("label")
        value = n.get("value")
        if not label or value is None:
            continue
        rows.append(
            {
                "slug": f"number-{i}",
                "title": f"By the numbers · {label}",
                "fact": f"World Cup 2026 — {label}: {value}.",
                "entities": ["2026", "stats", str(label)],
                "raw": n,
            }
        )

    for h in snap.get("hosts_detail") or []:
        nation = h.get("nation")
        note = h.get("note")
        if not nation or not note:
            continue
        rows.append(
            {
                "slug": f"host-{str(nation).lower().replace(' ', '-')}",
                "title": f"Host · {nation}",
                "fact": note if str(note).endswith(".") else f"{note}.",
                "entities": [nation, "hosts", "2026"],
                "raw": h,
            }
        )

    for first in (snap.get("format_facts") or {}).get("firsts") or []:
        slug = str(first).lower().replace(" ", "-")[:48]
        rows.append(
            {
                "slug": f"first-{slug}",
                "title": "2026 first",
                "fact": first if str(first).endswith(".") else f"{first}.",
                "entities": ["2026", "format", "first"],
                "raw": {"first": first},
            }
        )

    if snap.get("headline"):
        headline = snap["headline"]
        rows.append(
            {
                "slug": "headline",
                "title": "Current headline",
                "fact": headline if str(headline).endswith(".") else f"{headline}.",
                "entities": ["2026", "headline"],
                "raw": {"headline": headline},
            }
        )

    if snap.get("final_date") and snap.get("final_venue"):
        rows.append(
            {
                "slug": "final-meta",
                "title": "2026 Final",
                "fact": (
                    f"The World Cup 2026 Final is scheduled for {snap['final_date']} "
                    f"at {snap['final_venue']}."
                ),
                "entities": ["2026", "final", snap["final_venue"]],
                "raw": {"final_date": snap["final_date"], "final_venue": snap["final_venue"]},
            }
        )

    return rows


async def _upsert_knowledge(
    db: AsyncSession,
    *,
    source_url: str,
    title: str,
    category: str,
    fact: str,
    entities: list,
    raw: dict,
) -> tuple[KnowledgeEntry, bool]:
    existing = await db.scalar(select(KnowledgeEntry).where(KnowledgeEntry.source_url == source_url))
    if existing:
        existing.title = title[:512]
        existing.category = category
        existing.fact = fact
        existing.raw_excerpt = json.dumps(raw)
        existing.entities = [str(e) for e in entities if e]
        existing.confidence = 1.0
        await db.flush()
        return existing, False
    entry = KnowledgeEntry(
        scrape_job_id=None,
        source_url=source_url,
        title=title[:512],
        category=category,
        fact=fact,
        raw_excerpt=json.dumps(raw),
        entities=[str(e) for e in entities if e],
        confidence=1.0,
    )
    db.add(entry)
    await db.flush()
    return entry, True


async def _ensure_mcq(
    db: AsyncSession,
    *,
    prompt: str,
    correct: str,
    distractors: list[str],
    challenge_type: ChallengeType,
    source_url: str,
    knowledge_entry_id: str,
    tags: list[str],
    memory_payload: dict | None = None,
    difficulty: str = "medium",
) -> bool:
    dup = await db.execute(select(Question).where(Question.prompt == prompt).limit(1))
    if dup.scalar_one_or_none():
        return False
    opts = [{"label": correct, "is_correct": True}] + [
        {"label": d, "is_correct": False} for d in distractors[:3]
    ]
    q = Question(
        challenge_type=challenge_type,
        prompt=prompt,
        memory_payload=memory_payload,
        difficulty=difficulty,
        source="bootstrap-2026",
        source_url=source_url,
        knowledge_entry_id=knowledge_entry_id,
        approved=True,
        tags=tags,
    )
    db.add(q)
    await db.flush()
    for i, opt in enumerate(opts):
        db.add(
            QuestionOption(
                question_id=q.id,
                label=opt["label"][:256],
                is_correct=bool(opt["is_correct"]),
                sort_order=i,
            )
        )
    return True


async def bootstrap_world_cup_knowledge(db: AsyncSession) -> dict:
    """Idempotent: insert history facts + questions if not already bootstrapped."""
    existing = await db.scalar(
        select(func.count())
        .select_from(KnowledgeEntry)
        .where(KnowledgeEntry.source_url.like(f"{SOURCE_PREFIX_HISTORY}%"))
    )
    if existing and existing > 0:
        return {"skipped": True, "knowledge": existing, "questions": 0}

    tournaments = _load_history()
    if not tournaments:
        return {"skipped": True, "knowledge": 0, "questions": 0, "reason": "no_data"}

    knowledge_n = 0
    questions_n = 0

    for t in tournaments:
        year = t.get("year")
        winner = t.get("winner")
        host = t.get("host")
        if not year or not winner:
            continue

        fact_parts = [f"{winner} won the FIFA World Cup in {year}"]
        if host:
            fact_parts.append(f"hosted by {host}")
        if t.get("final"):
            fact_parts.append(f"final: {t['final']}")
        if t.get("notes"):
            fact_parts.append(t["notes"])
        fact = ". ".join(fact_parts) + "."
        source_url = f"{SOURCE_PREFIX_HISTORY}{year}"

        entry = KnowledgeEntry(
            scrape_job_id=None,
            source_url=source_url,
            title=f"World Cup {year}",
            category="world-cup-history",
            fact=fact,
            raw_excerpt=json.dumps(t),
            entities=[str(x) for x in (winner, host, year) if x],
            confidence=1.0,
        )
        db.add(entry)
        await db.flush()
        knowledge_n += 1

        distractors = [d for d in DISTRACTORS if d.lower() != str(winner).lower()][:3]
        options = [{"label": str(winner), "is_correct": True}] + [
            {"label": d, "is_correct": False} for d in distractors
        ]
        rotate = int(year) % 4
        options = options[rotate:] + options[:rotate]

        prompt = f"Which nation won the FIFA World Cup in {year}?"
        dup = await db.execute(select(Question).where(Question.prompt == prompt).limit(1))
        if not dup.scalar_one_or_none():
            q = Question(
                challenge_type=ChallengeType.FOOTBALL,
                prompt=prompt,
                difficulty="easy",
                source="bootstrap",
                source_url=source_url,
                knowledge_entry_id=entry.id,
                approved=True,
                tags=["bootstrap", "world-cup", str(year)],
            )
            db.add(q)
            await db.flush()
            for i, opt in enumerate(options):
                db.add(
                    QuestionOption(
                        question_id=q.id,
                        label=opt["label"][:256],
                        is_correct=bool(opt["is_correct"]),
                        sort_order=i,
                    )
                )
            questions_n += 1

        mem_prompt = f"From the facts shown, who won the World Cup in {year}?"
        dup_m = await db.execute(select(Question).where(Question.prompt == mem_prompt).limit(1))
        if not dup_m.scalar_one_or_none():
            mq = Question(
                challenge_type=ChallengeType.MEMORY,
                prompt=mem_prompt,
                memory_payload={
                    "title": f"World Cup {year}",
                    "facts": [fact, f"Host: {host}" if host else "World Cup history"],
                    "display_seconds": 10,
                },
                difficulty="medium",
                source="bootstrap",
                source_url=source_url,
                knowledge_entry_id=entry.id,
                approved=True,
                tags=["bootstrap", "memory", str(year)],
            )
            db.add(mq)
            await db.flush()
            for i, opt in enumerate(options):
                db.add(
                    QuestionOption(
                        question_id=mq.id,
                        label=opt["label"][:256],
                        is_correct=bool(opt["is_correct"]),
                        sort_order=i,
                    )
                )
            questions_n += 1

    await db.flush()
    logger.info("Bootstrapped world cup knowledge: %s facts, %s questions", knowledge_n, questions_n)
    return {"skipped": False, "knowledge": knowledge_n, "questions": questions_n}


async def bootstrap_world_cup_2026_knowledge(db: AsyncSession) -> dict:
    """Refresh current WC 2026 fun facts + data into the shared agent knowledge bank."""
    snap = _load_2026()
    if not snap:
        return {"skipped": True, "knowledge": 0, "questions": 0, "reason": "no_data"}

    rows = _facts_from_2026(snap)
    if not rows:
        return {"skipped": True, "knowledge": 0, "questions": 0, "reason": "empty_facts"}

    live_urls = {f"{SOURCE_PREFIX_2026}{r['slug']}" for r in rows}
    old = (
        await db.execute(
            select(KnowledgeEntry).where(KnowledgeEntry.source_url.like(f"{SOURCE_PREFIX_2026}%"))
        )
    ).scalars().all()
    stale_ids = [e.id for e in old if e.source_url not in live_urls]
    if stale_ids:
        stale_qs = (
            await db.execute(select(Question).where(Question.knowledge_entry_id.in_(stale_ids)))
        ).scalars().all()
        stale_q_ids = [q.id for q in stale_qs]
        if stale_q_ids:
            await db.execute(delete(QuestionOption).where(QuestionOption.question_id.in_(stale_q_ids)))
            await db.execute(delete(Question).where(Question.id.in_(stale_q_ids)))
        await db.execute(delete(KnowledgeEntry).where(KnowledgeEntry.id.in_(stale_ids)))

    inserted = 0
    updated = 0
    questions_n = 0
    last_entry: KnowledgeEntry | None = None
    for r in rows:
        source_url = f"{SOURCE_PREFIX_2026}{r['slug']}"
        entry, created = await _upsert_knowledge(
            db,
            source_url=source_url,
            title=r["title"],
            category="world-cup-2026",
            fact=r["fact"],
            entities=r.get("entities") or ["2026"],
            raw=r.get("raw") or {},
        )
        last_entry = entry
        if created:
            inserted += 1
        else:
            updated += 1

    if last_entry is None:
        return {"skipped": True, "knowledge": 0, "questions": 0, "reason": "no_entries"}

    gb_list = snap.get("golden_boot") or []
    gb = gb_list[0] if gb_list else {}
    if gb.get("player"):
        gb_entry = await db.scalar(
            select(KnowledgeEntry).where(KnowledgeEntry.source_url == f"{SOURCE_PREFIX_2026}golden-boot-1")
        )
        if gb_entry and await _ensure_mcq(
            db,
            prompt="Who leads (or co-leads) the World Cup 2026 Golden Boot race as of the latest Arena64 snapshot?",
            correct=str(gb["player"]),
            distractors=[
                x["player"] for x in gb_list[1:4] if x.get("player")
            ]
            or ["Harry Kane", "Erling Haaland", "Vinícius Jr."],
            challenge_type=ChallengeType.FOOTBALL,
            source_url=f"{SOURCE_PREFIX_2026}golden-boot-1",
            knowledge_entry_id=gb_entry.id,
            tags=["bootstrap-2026", "golden-boot", "2026"],
            difficulty="medium",
        ):
            questions_n += 1

    hosts = snap.get("hosts") or []
    hosts_entry = await db.scalar(
        select(KnowledgeEntry).where(KnowledgeEntry.source_url == f"{SOURCE_PREFIX_2026}hosts")
    )
    if len(hosts) >= 3 and hosts_entry:
        if await _ensure_mcq(
            db,
            prompt="Which three nations co-host the 2026 FIFA World Cup?",
            correct=", ".join(hosts),
            distractors=[
                "USA, Brazil, Argentina",
                "Canada, Brazil, Mexico",
                "USA, England, Mexico",
            ],
            challenge_type=ChallengeType.FOOTBALL,
            source_url=f"{SOURCE_PREFIX_2026}hosts",
            knowledge_entry_id=hosts_entry.id,
            tags=["bootstrap-2026", "hosts", "2026"],
            difficulty="easy",
        ):
            questions_n += 1

    final_entry = await db.scalar(
        select(KnowledgeEntry).where(KnowledgeEntry.source_url == f"{SOURCE_PREFIX_2026}final-meta")
    )
    if snap.get("final_venue") and final_entry:
        if await _ensure_mcq(
            db,
            prompt="Where is the 2026 FIFA World Cup Final scheduled to be played?",
            correct=str(snap["final_venue"]),
            distractors=["Dallas Stadium", "Miami Stadium", "Los Angeles Stadium"],
            challenge_type=ChallengeType.STADIUM,
            source_url=f"{SOURCE_PREFIX_2026}final-meta",
            knowledge_entry_id=final_entry.id,
            tags=["bootstrap-2026", "venues", "2026"],
            difficulty="medium",
        ):
            questions_n += 1

    format_entry = await db.scalar(
        select(KnowledgeEntry).where(KnowledgeEntry.source_url == f"{SOURCE_PREFIX_2026}format")
    )
    if format_entry and await _ensure_mcq(
        db,
        prompt="How many teams are in the 2026 FIFA World Cup finals?",
        correct="48",
        distractors=["32", "40", "64"],
        challenge_type=ChallengeType.FOOTBALL,
        source_url=f"{SOURCE_PREFIX_2026}format",
        knowledge_entry_id=format_entry.id,
        tags=["bootstrap-2026", "format", "2026"],
        difficulty="easy",
    ):
        questions_n += 1

    fun = [f["fact"] for f in (snap.get("fun_facts") or [])[:4] if f.get("fact")]
    if fun and hosts_entry:
        mem_prompt = "From the 2026 facts shown, which nation is NOT a co-host of this World Cup?"
        if await _ensure_mcq(
            db,
            prompt=mem_prompt,
            correct="Brazil",
            distractors=["Canada", "Mexico", "United States"],
            challenge_type=ChallengeType.MEMORY,
            source_url=f"{SOURCE_PREFIX_2026}hosts",
            knowledge_entry_id=hosts_entry.id,
            tags=["bootstrap-2026", "memory", "2026"],
            memory_payload={
                "title": "World Cup 2026 hosts",
                "facts": fun,
                "display_seconds": 12,
            },
            difficulty="medium",
        ):
            questions_n += 1

    await db.flush()
    total = await db.scalar(
        select(func.count())
        .select_from(KnowledgeEntry)
        .where(KnowledgeEntry.category == "world-cup-2026")
    )
    logger.info(
        "Bootstrapped WC 2026 knowledge: inserted=%s updated=%s questions=%s total=%s",
        inserted,
        updated,
        questions_n,
        total,
    )
    return {
        "skipped": False,
        "inserted": inserted,
        "updated": updated,
        "knowledge": total or 0,
        "questions": questions_n,
    }


async def bootstrap_all_world_cup_knowledge(db: AsyncSession) -> dict:
    """History (once) + current 2026 snapshot (refreshable)."""
    history = await bootstrap_world_cup_knowledge(db)
    current = await bootstrap_world_cup_2026_knowledge(db)
    return {"history": history, "world_cup_2026": current}
