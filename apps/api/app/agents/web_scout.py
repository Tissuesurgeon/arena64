"""Web Scout Agent — free DuckDuckGo search → scrape football platforms → Qwen LLM facts → DB."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Optional
from urllib.parse import parse_qs, unquote, urlparse

import httpx

from app.core.config import get_settings
from app.integrations.llm import chat_with_fallback
from app.prompts import load_prompt

try:
    from bs4 import BeautifulSoup  # type: ignore

    _HAS_BS4 = True
except ImportError:  # pragma: no cover
    BeautifulSoup = None  # type: ignore
    _HAS_BS4 = False


# Football news + data platforms (no Wikipedia, no paid football APIs).
DEFAULT_FOOTBALL_HOSTS = [
    "www.espn.com",
    "espn.com",
    "www.bbc.com",
    "bbc.com",
    "www.goal.com",
    "goal.com",
    "www.fifa.com",
    "fifa.com",
    "www.skysports.com",
    "skysports.com",
    "www.transfermarkt.com",
    "transfermarkt.com",
    "www.reuters.com",
    "reuters.com",
    "www.theguardian.com",
    "theguardian.com",
    "www.cbssports.com",
    "cbssports.com",
    "www.marca.com",
    "marca.com",
    "www.mlssoccer.com",
    "mlssoccer.com",
    "www.uefa.com",
    "uefa.com",
    "www.flashscore.com",
    "flashscore.com",
    "www.sofascore.com",
    "sofascore.com",
    "www.whoscored.com",
    "whoscored.com",
]

# Used only if search returns nothing (still football platforms, never Wikipedia).
FALLBACK_SEED_URLS = [
    "https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026",
    "https://www.fifa.com/en/tournaments/mens/worldcup",
    "https://www.espn.com/soccer/league/_/name/fifa.world",
    "https://www.bbc.com/sport/football/world-cup",
    "https://www.goal.com/en/news",
    "https://www.skysports.com/world-cup",
    "https://www.transfermarkt.com/weltmeisterschaft-2026/startseite/pokalwettbewerb/WM26",
]

DEFAULT_SEARCH_QUERIES = [
    "FIFA World Cup 2026 semi-finals results",
    "FIFA World Cup 2026 Golden Boot standings",
    "World Cup 2026 France Spain England Argentina",
    "FIFA World Cup 2026 hosts Canada Mexico USA fun facts",
    "World Cup 2026 Round of 32 format 48 teams",
    "FIFA World Cup 2026 Final New York New Jersey Stadium",
    "World Cup 2026 Mbappé Messi Haaland goals",
    "FIFA World Cup 2026 quarter-final results",
]

BLOCKED_HOST_FRAGMENTS = ("wikipedia.org", "wikimedia.org", "wikiwand.com")

USER_AGENT = (
    "Mozilla/5.0 (compatible; Arena64WebScout/1.0; +https://github.com/arena64; "
    "educational tournament quiz research bot)"
)

DISTRACTOR_POOL = [
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
    "Mexico",
    "Croatia",
    "Belgium",
    "Sweden",
    "Japan",
    "Morocco",
]


class WebScoutAgent:
    """
    Free web search (DuckDuckGo HTML) for football news & data pages,
    scrape allowlisted platforms, store facts, generate quiz questions.
    No paid APIs.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self._last_llm_provider: str | None = None

    @property
    def allowed_hosts(self) -> set[str]:
        raw = self.settings.scout_allowed_hosts.strip()
        if not raw:
            return set(DEFAULT_FOOTBALL_HOSTS)
        return {h.strip().lower() for h in raw.split(",") if h.strip()}

    def _host(self, url: str) -> str:
        return urlparse(url).netloc.lower().removeprefix("www.")

    def _is_blocked(self, url: str) -> bool:
        host = urlparse(url).netloc.lower()
        return any(b in host for b in BLOCKED_HOST_FRAGMENTS)

    def _host_allowed(self, url: str) -> bool:
        if self._is_blocked(url):
            return False
        host = urlparse(url).netloc.lower()
        bare = host.removeprefix("www.")
        allowed = self.allowed_hosts
        return any(
            host == a or bare == a.removeprefix("www.") or host.endswith("." + a.removeprefix("www."))
            for a in allowed
        )

    def _site_bias_query(self, query: str) -> str:
        """Bias free web search toward football news/data platforms (no paid APIs)."""
        return (
            f"{query} (World Cup OR FIFA) "
            "(site:espn.com OR site:bbc.com OR site:goal.com OR site:fifa.com OR "
            "site:skysports.com OR site:transfermarkt.com OR site:reuters.com OR "
            "site:theguardian.com OR site:uefa.com OR site:flashscore.com OR "
            "site:sofascore.com OR site:whoscored.com OR espn OR bbc OR goal OR fifa)"
        )

    async def search_web(self, client: httpx.AsyncClient, query: str, num: int = 8) -> list[str]:
        """Free DuckDuckGo HTML search — no API keys, no paid search APIs."""
        q = self._site_bias_query(query)
        r = await client.get(
            "https://html.duckduckgo.com/html/",
            params={"q": q},
            headers={"User-Agent": USER_AGENT},
        )
        if r.status_code >= 400:
            return []
        html = r.text
        urls: list[str] = []
        for m in re.finditer(r'href="(/l/\?[^"]+uddg=[^"]+|https?://[^"]+)"', html):
            href = m.group(1)
            if href.startswith("/l/?"):
                qs = parse_qs(urlparse("https://duckduckgo.com" + href).query)
                encoded = (qs.get("uddg") or [None])[0]
                if not encoded:
                    continue
                href = unquote(encoded)
            if not href.startswith("http"):
                continue
            if self._host_allowed(href):
                urls.append(href.split("#")[0])
            if len(urls) >= num:
                break
        seen: set[str] = set()
        out: list[str] = []
        for u in urls:
            if u in seen:
                continue
            seen.add(u)
            out.append(u)
        return out

    async def discover_urls(
        self,
        client: httpx.AsyncClient,
        topic: str,
        queries: Optional[list[str]] = None,
        max_urls: int = 12,
    ) -> tuple[list[str], dict]:
        """Discover football news/data URLs via free DuckDuckGo search (no paid APIs)."""
        meta: dict = {"search_engine": None, "queries": [], "paid_apis": False}
        found: list[str] = []
        seen: set[str] = set()
        qlist = queries or [f"{topic} {q}" if topic not in q else q for q in DEFAULT_SEARCH_QUERIES]

        for q in qlist:
            meta["queries"].append(q)
            urls = await self.search_web(client, q)
            if urls:
                meta["search_engine"] = "duckduckgo"
            for u in urls:
                if u in seen or self._is_blocked(u):
                    continue
                if not self._host_allowed(u):
                    continue
                seen.add(u)
                found.append(u)
                if len(found) >= max_urls:
                    return found, meta

        if not found:
            meta["search_engine"] = "fallback_seeds"
            for u in FALLBACK_SEED_URLS:
                if self._host_allowed(u) and u not in seen:
                    found.append(u)
        return found[:max_urls], meta

    async def fetch_page(self, client: httpx.AsyncClient, url: str) -> tuple[str, str]:
        if not self._host_allowed(url):
            raise ValueError(f"Host not allowlisted or blocked: {url}")
        r = await client.get(url, follow_redirects=True)
        r.raise_for_status()
        html = r.text
        if _HAS_BS4 and BeautifulSoup is not None:
            try:
                soup = BeautifulSoup(html, "lxml")
            except Exception:
                soup = BeautifulSoup(html, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "aside", "iframe", "noscript"]):
                tag.decompose()
            title = (soup.title.string or "").strip() if soup.title else url
            content = (
                soup.select_one("article")
                or soup.select_one("[itemprop=articleBody]")
                or soup.select_one("main")
                or soup.body
                or soup
            )
            text = content.get_text("\n", strip=True)
        else:
            title_m = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.I | re.S)
            title = re.sub(r"\s+", " ", title_m.group(1)).strip() if title_m else url
            text = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", html)
            text = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", text)
            text = re.sub(r"(?is)<[^>]+>", "\n", text)
            text = re.sub(r"[ \t]+", " ", text)
            text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)[:12000]
        return title, text

    def extract_facts(self, title: str, text: str, url: str) -> list[dict]:
        facts: list[dict] = []
        lines = [ln.strip() for ln in text.split("\n") if len(ln.strip()) > 40]

        year_winner = re.findall(
            r"(19\d{2}|20\d{2}).{0,60}?(?:won by|winner[s]?:?\s*|champions?\s+|beat|defeated)\s*"
            r"([A-Z][A-Za-z\s\-]+)",
            text,
            flags=re.IGNORECASE,
        )
        for year, nation in year_winner[:12]:
            nation = nation.strip().split(".")[0][:40]
            facts.append(
                {
                    "fact": f"In {year}, {nation} won the FIFA World Cup.",
                    "title": title,
                    "category": "champions",
                    "entities": [year, nation],
                    "raw_excerpt": f"{year} {nation}",
                    "source_url": url,
                    "confidence": 0.75,
                }
            )

        keywords = ("World Cup", "FIFA", "final", "champion", "Golden Boot", "host")
        for ln in lines:
            if not any(k.lower() in ln.lower() for k in keywords):
                continue
            if not re.search(r"(19|20)\d{2}", ln) and "World Cup" not in ln:
                continue
            clean = re.sub(r"\[\d+\]", "", ln)
            if len(clean) > 220:
                clean = clean[:217] + "..."
            facts.append(
                {
                    "fact": clean,
                    "title": title,
                    "category": "world-cup-2026" if "2026" in clean else "football-news",
                    "entities": re.findall(r"(19|20)\d{2}", clean)[:3],
                    "raw_excerpt": clean[:400],
                    "source_url": url,
                    "confidence": 0.65,
                }
            )
            if len(facts) >= 40:
                break

        seen: set[str] = set()
        unique: list[dict] = []
        for f in facts:
            key = f["fact"].lower()
            if key in seen:
                continue
            seen.add(key)
            unique.append(f)
        return unique[:25]

    async def llm_enrich_facts(self, title: str, text: str, url: str) -> list[dict]:
        """Extract structured facts via Voya-style chat_with_fallback (Ollama → Qwen → None)."""
        system = load_prompt("web_scout")
        user = (
            f"Title: {title}\nURL: {url}\n\n"
            f"Article:\n{text[:8000]}\n\n"
            'Respond with JSON only: {"facts":[{"fact":"...","category":"...","entities":["..."]}]}'
        )
        result = await chat_with_fallback(
            system=system,
            user=user,
            json_mode=True,
            temperature=0.2,
            max_tokens=1024,
        )
        if not result:
            return []
        content, provider = result
        self._last_llm_provider = provider
        try:
            start_obj, end_obj = content.find("{"), content.rfind("}")
            start_arr, end_arr = content.find("["), content.rfind("]")
            items: list = []
            if start_obj != -1 and end_obj > start_obj and (start_arr == -1 or start_obj < start_arr):
                data = json.loads(content[start_obj : end_obj + 1])
                items = data.get("facts") if isinstance(data, dict) else []
                if not isinstance(items, list):
                    items = []
            elif start_arr != -1 and end_arr > start_arr:
                items = json.loads(content[start_arr : end_arr + 1])
            else:
                return []
            out: list[dict] = []
            for item in items[:12]:
                if not isinstance(item, dict):
                    continue
                fact = str(item.get("fact", "")).strip()
                if len(fact) < 20:
                    continue
                out.append(
                    {
                        "fact": fact,
                        "title": title,
                        "category": item.get("category") or "football-news",
                        "entities": item.get("entities") or [],
                        "raw_excerpt": fact,
                        "source_url": url,
                        "confidence": 0.88,
                        "llm_provider": provider,
                    }
                )
            return out
        except Exception:
            return []

    def fact_to_questions(self, entry: object) -> list[dict]:
        fact = getattr(entry, "fact", "")
        title = getattr(entry, "title", "") or "Football Fact Card"
        source_url = getattr(entry, "source_url", "")
        questions: list[dict] = []
        year_match = re.search(r"(19\d{2}|20\d{2})", fact)
        nation_match = re.search(
            r"\b(Brazil|Germany|Argentina|France|Italy|Spain|England|Netherlands|Uruguay|Portugal|"
            r"Mexico|Croatia|Belgium|Sweden|Japan|Morocco|South Africa|South Korea|USA|United States|"
            r"West Germany|Soviet Union|Czechoslovakia)\b",
            fact,
            flags=re.IGNORECASE,
        )

        if year_match and nation_match and "won" in fact.lower():
            year = year_match.group(1)
            correct = nation_match.group(1)
            distractors = [d for d in DISTRACTOR_POOL if d.lower() != correct.lower()][:3]
            options = [{"label": correct, "is_correct": True}] + [
                {"label": d, "is_correct": False} for d in distractors
            ]
            rotate = int(year) % 4
            options = options[rotate:] + options[:rotate]
            questions.append(
                {
                    "challenge_type": "FOOTBALL",
                    "prompt": f"Which nation won the FIFA World Cup in {year}?",
                    "difficulty": "easy",
                    "tags": ["scout", "champions", year],
                    "options": options,
                    "memory_payload": None,
                }
            )
            questions.append(
                {
                    "challenge_type": "MEMORY",
                    "prompt": f"From the facts shown, who won the World Cup in {year}?",
                    "difficulty": "medium",
                    "tags": ["scout", "memory", year],
                    "memory_payload": {
                        "title": title,
                        "facts": [fact, f"Source: {source_url}"],
                        "display_seconds": 10,
                    },
                    "options": options,
                }
            )
        else:
            snippet = fact if len(fact) < 160 else fact[:157] + "..."
            wrong = [
                "This event never occurred in World Cup history.",
                "The statement refers to the UEFA Champions League, not the World Cup.",
                "The year and winner in the statement are reversed.",
            ]
            questions.append(
                {
                    "challenge_type": "FOOTBALL",
                    "prompt": "Which statement is accurate?",
                    "difficulty": "medium",
                    "tags": ["scout", "general"],
                    "options": [
                        {"label": snippet, "is_correct": True},
                        {"label": wrong[0], "is_correct": False},
                        {"label": wrong[1], "is_correct": False},
                        {"label": wrong[2], "is_correct": False},
                    ],
                    "memory_payload": None,
                }
            )
        return questions

    async def store_fact(self, db, job_id: str, payload: dict, *, topic: str = "world-cup"):
        from sqlalchemy import select

        from app.models import KnowledgeEntry

        fact = (payload.get("fact") or "").strip()
        source_url = payload.get("source_url") or ""
        if not fact:
            return None
        dup = await db.execute(select(KnowledgeEntry).where(KnowledgeEntry.fact == fact).limit(1))
        if dup.scalar_one_or_none():
            return None

        default_cat = (
            "world-cup-2026"
            if topic in ("world-cup", "world-cup-2026") or "2026" in (topic or "")
            else "football-news"
        )
        entry = KnowledgeEntry(
            scrape_job_id=job_id,
            source_url=source_url,
            title=payload.get("title") or "",
            category=payload.get("category") or default_cat,
            fact=fact,
            raw_excerpt=payload.get("raw_excerpt"),
            entities=payload.get("entities") or [],
            confidence=float(payload.get("confidence") or 0.7),
        )
        db.add(entry)
        await db.flush()
        return entry

    async def store_questions_from_entry(self, db, entry, auto_approve: bool) -> int:
        from sqlalchemy import select

        from app.models import ChallengeType, Question, QuestionOption

        created = 0
        for qpayload in self.fact_to_questions(entry):
            existing = await db.execute(select(Question).where(Question.prompt == qpayload["prompt"]).limit(1))
            if existing.scalar_one_or_none():
                continue
            ctype = qpayload["challenge_type"]
            if isinstance(ctype, str):
                ctype = ChallengeType(ctype)
            q = Question(
                challenge_type=ctype,
                prompt=qpayload["prompt"],
                memory_payload=qpayload.get("memory_payload"),
                difficulty=qpayload.get("difficulty", "medium"),
                source="web_scout",
                source_url=entry.source_url,
                knowledge_entry_id=entry.id,
                approved=auto_approve,
                tags=qpayload.get("tags") or ["scout"],
            )
            db.add(q)
            await db.flush()
            for i, opt in enumerate(qpayload["options"]):
                db.add(
                    QuestionOption(
                        question_id=q.id,
                        label=opt["label"][:256],
                        is_correct=bool(opt["is_correct"]),
                        sort_order=i,
                    )
                )
            created += 1
        return created

    async def run(
        self,
        db,
        topic: str = "world-cup",
        urls: Optional[list[str]] = None,
        queries: Optional[list[str]] = None,
        auto_approve: bool = False,
    ):
        from app.models import ScrapeJob

        job = ScrapeJob(
            status="running",
            topic=topic,
            urls=urls or [],
            meta={
                "agent": "web_scout",
                "paid_apis": False,
                "search": "duckduckgo",
                "ai_provider": self.settings.cloud_ai_provider,
                "ollama_model": self.settings.ollama_model,
                "qwen_chat_model": self.settings.qwen_chat_model,
            },
        )
        db.add(job)
        await db.flush()

        pages = 0
        facts_n = 0
        questions_n = 0

        try:
            async with httpx.AsyncClient(
                timeout=45,
                headers={"User-Agent": USER_AGENT, "Accept-Language": "en"},
            ) as client:
                if urls:
                    target_urls = [u for u in urls if self._host_allowed(u) and not self._is_blocked(u)]
                    search_meta = {"search_engine": "manual_urls", "queries": []}
                else:
                    target_urls, search_meta = await self.discover_urls(client, topic, queries=queries)
                job.urls = target_urls
                job.meta = {**(job.meta or {}), **search_meta}

                for url in target_urls:
                    try:
                        title, text = await self.fetch_page(client, url)
                    except Exception as exc:  # noqa: BLE001
                        job.meta = {**(job.meta or {}), f"error:{url}": str(exc)[:200]}
                        continue

                    pages += 1
                    extracted = self.extract_facts(title, text, url)
                    enriched = await self.llm_enrich_facts(title, text, url)
                    # Prefer Qwen facts when available; always keep heuristics as backup
                    combined = enriched if enriched else extracted
                    if enriched and extracted:
                        # Merge unique heuristic facts Qwen may have missed
                        seen_facts = {f["fact"].lower() for f in enriched}
                        for f in extracted:
                            if f["fact"].lower() not in seen_facts:
                                combined.append(f)
                    for payload in combined:
                        entry = await self.store_fact(db, job.id, payload, topic=topic)
                        if entry is None:
                            continue
                        facts_n += 1
                        questions_n += await self.store_questions_from_entry(db, entry, auto_approve)

            job.pages_scraped = pages
            job.facts_stored = facts_n
            job.questions_created = questions_n
            job.status = "completed"
            job.finished_at = datetime.utcnow()
            if self._last_llm_provider:
                job.meta = {**(job.meta or {}), "llm_provider": self._last_llm_provider}
            else:
                job.meta = {**(job.meta or {}), "llm_provider": "heuristics"}
        except Exception as exc:  # noqa: BLE001
            job.status = "failed"
            job.error = str(exc)[:1000]
            job.finished_at = datetime.utcnow()

        await db.flush()
        return job


web_scout_agent = WebScoutAgent()

# Back-compat export for admin "sources" endpoint
DEFAULT_SCOUT_URLS = FALLBACK_SEED_URLS
DEFAULT_SEARCH_QUERIES_EXPORT = DEFAULT_SEARCH_QUERIES
