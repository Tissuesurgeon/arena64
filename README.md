# Arena64

**Coach the agent. Compete the Arena.**

### Injective Global Cup Hackathon 2026

Arena64 is an **AI Agent Arena** for World Cup–inspired competitions. Users are **coaches**: each wallet owns one persistent football-intelligence agent that competes autonomously. The platform opens **6-agent Arena Cups**; coaches join, configure strategy, fund the ledger, and **spectate** — agents make every competitive decision.

It demonstrates **x402**, **USDC CCTP**, **MCP Server**, and **Agent Skills** for AI-to-service interactions on Injective.

It is **not** a betting platform, prediction market, or FIFA product.

---

## Overview

Arena64 is an AI agent competition platform where coaches create autonomous football intelligence agents, configure their strategic behavior, and deploy them into World Cup–inspired tournaments.

Unlike traditional trivia games where humans answer questions, Arena64 turns users into AI coaches. Every participant owns a persistent AI agent that competes by making decisions, managing resources, and answering football challenges without human intervention during live matches.

For the hackathon MVP, each cup fields **six human coaches’ agents**. Competition runs group stage → Semi Finals → Final. The **platform room agent** always keeps one open cup; when a room fills, the bracket starts and a new empty room opens immediately.

Arena64 demonstrates how autonomous AI agents can participate in structured competitions while leveraging Injective’s latest technologies (x402, USDC CCTP, MCP Server, and Agent Skills).

---

## Problem statement

Every World Cup attracts millions of fans who consume football through broadcasts, social media, fantasy leagues, and prediction platforms. Those experiences are largely **passive**: fans watch, click trivia manually, or stay glued to prediction UIs.

Autonomous AI agents can already make independent decisions, manage resources, and call external services. Arena64 asks:

**What if AI agents — not humans — became the competitors?**

Users design intelligent agents. Competition shifts from human recall to **AI strategy, resource management, and autonomous decision-making**.

---

## Vision

Arena64 aims to be a benchmark for autonomous AI competitions. Persistent agents should:

- Make independent decisions
- Execute configurable strategies
- Use external tools (MCP)
- Purchase premium AI services (x402)
- Learn from previous cups via memory
- Improve long-term performance

The World Cup–inspired arena is the first competitive environment for these agents.

---

## Core concept

Every connected wallet owns **one persistent AI agent** (until deleted). Users do not compete directly — they configure strategy before kickoff. During competition the agent decides using:

- Configured strategy
- Tournament memory
- Available ledger resources
- MCP research tools
- Optional premium (x402) insights

After the Final, career stats and memory roll up so the agent can improve next cup.

---

## User journey

1. Connect wallet (Injective EVM testnet).
2. Create an AI agent.
3. Configure a Strategy Profile.
4. Fund the **Arena64 Account** with testnet USDC (on-chain deposit or CCTP; use **Sync deposits** if needed).
5. Join an open **Arena Cup** on the tournament board.
6. Watch the agent compete autonomously (spectator UI — no answer buttons).
7. Review results, rewards, and career / memory.

No manual gameplay during the tournament. The agent owns every competitive decision.

| Coach does | Agent does |
|------------|------------|
| Connect wallet, create agent | Answers shared MCQs in live matches |
| Edit Strategy Profile | Applies confidence / risk / MCP / x402 budgets |
| Fund Arena64 Account | Competes through group → SF → Final |
| Join open Arena Cup & **spectate** | Logs decisions for explainability |
| Claim rewards, review career | Memory rollup after the Final |

---

## AI agent design

### Identity

Persistent identity: name, wallet owner, creation date, career statistics, Arena Rating.

### Strategy Profile

Coaches configure behavior (not knowledge):

- Confidence threshold
- Thinking time
- Risk preference
- Maximum MCP usage
- Premium insight budget
- Resource conservation

All competitors share the same football knowledge; strategy differentiates play. Strategy **locks** when a cup kicks off.

### Shared knowledge

Identical bank for all agents: World Cup history, teams, players, managers, stadiums, records, rules. Challenge packs: **FOOTBALL · MEMORY · STADIUM · PLAYER_ID · FLAG · FORMATION**.

### Memory

Tournament experience is summarized into lessons (category strengths/weaknesses, spend efficiency, speed) that shape future strategy application.

### Decision engine

1. Read the question  
2. Estimate confidence  
3. Review memory  
4. Decide whether MCP research is needed  
5. Decide whether to buy premium insight (x402)  
6. Select an answer  
7. Store the experience  

---

## Tournament structure (MVP)

The **platform room agent** always keeps one open public **Arena Cup** (6 seats, humans only). **No system fillers.** Users cannot create cups.

`Lobby (6) → 2 groups of 3 → Semi Finals → Final`

When the sixth coach joins, the bracket forms, matches go LIVE for the AI runtime, and a **new empty Arena Cup** opens immediately.

All agents in a match receive **identical questions simultaneously**. Advancement is by match score.

---

## Challenge format

Multiple-choice football challenges (typically four options). Performance depends on autonomous decision-making under shared information and strategy budgets.

Scoring: correct = `100 + remaining_seconds × 2`. Rewards after platform fee: **55% / 25% / 12% / 8%**.

---

## Persistent careers

Stats persist across cups: tournaments, matches, wins, championships, accuracy, response time, resource efficiency, Arena Rating.

---

## Fair competition

All agents start with identical knowledge. Differences come only from strategy, memory, resource management, decision quality, and autonomous reasoning.

---

## How Injective technologies are used

Required for [Injective Global Cup](https://www.hackquest.io/hackathons/The-Injective-Global-Cup) README clarity:

| Technology | How Arena64 uses it |
|------------|---------------------|
| **Wallet** | Coach identity on Injective EVM testnet (`1439`) → one agent per wallet |
| **USDC / CCTP** | EOA → treasury ERC-20 deposit or CCTP burn (+ Iris) → **Available**; join locks → **Locked**; withdraw returns Available to EOA |
| **x402** | Mid-match premium insight + coach credit packs via facilitator verify |
| **MCP Server** | [`apps/mcp-server`](apps/mcp-server) — `researchByCategory`, `buyPremiumInsight`, standings, agent/strategy tools |
| **Agent Skills** | [`packages/agent-skills`](packages/agent-skills) + ai-runtime `SkillsRegistry` (competitor, research, premium, director, …) |

Finance path:

```
Connected Wallet → Treasury → Arena64 Account (Available / Locked)
        → lock entry → Tournament Finance → settle / rewards
        → x402 premium debit → agent continues uninterrupted
```

See [`blockchain/README.md`](blockchain/README.md) for the judge env/ABI matrix.

---

## Quick start (prefer local DB for demos)

Remote Postgres adds multi-second latency — use local Docker Postgres for live hackathon demos.

```bash
cp .env.example .env
# Host port 15432 avoids clash with system Postgres on 5432
docker compose up -d postgres redis

# Point apps/api/.env DATABASE_URL at localhost:15432
cd apps/api
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# AI runtime (autonomous answers)
cd apps/ai-runtime
pip install -r requirements.txt
ARENA64_API_URL=http://127.0.0.1:8000 python main.py

cd apps/web
npm install && npm run dev
```

Or run runtime via compose: `docker compose up -d ai-runtime` (with API).

- Web: http://localhost:3000  
- API docs: http://localhost:8000/docs  
- Health: http://localhost:8000/health  

### Judge demo script

1. **Connect wallet** (Injective EVM testnet `1439`) → sign in  
2. **`/agent`** — create agent → **`/agent/strategy`** — confidence / risk / MCP / x402 budget  
3. **`/wallet`** — deposit testnet USDC (or CCTP); use **Sync deposits** if Available did not update  
4. **`/tournaments`** — join open **Arena Cup** (platform-opened, 6 agents)  
5. Lobby → watch agent → SpectatorHud (no answer buttons)  
6. Watch decision chips (MCP / x402 / reasoning) through SF → Final  
7. After Final → **`/agent/career`** + **`/rewards`**  
8. Optional: **`/trial`** — solo practice watch  
9. Point judges at [`blockchain/README.md`](blockchain/README.md), MCP server, and Agent Skills below  

**Connect Wallet** in the nav. Demo session remains available in development only.

---

## Architecture

Arena64 is **OpenClaw for competitive AI agents**: modular runtime (memory, skills, tools), **policy-driven** via a Strategy Engine — not a task planner.

```
arena64/
  apps/web/           Coach + SpectatorHud UI
  apps/api/           Identity, tournament, ledger, agents, room agent, memory
  apps/ai-runtime/    Competition runtime (Strategy → Memory → Skills → Decision)
  apps/mcp-server/    MCP tools (researchByCategory, buyPremiumInsight, …)
  packages/agent-skills/   competitor + football research + platform skills
  packages/prompts/        competitor.system.md
  blockchain/              Injective env/ABI matrix for judges
```

```
Coach UI ──► API (JWT) ──► TournamentDirector + room agent
                ▲                │
                │                ▼
           ai-runtime ◄── live-work / answers / decision logs
                │
           Strategy gate → skills (≤2) → re-decide → experience
```

**Platform services** (not competitors): Tournament Director, room agent (`tournament_room_agent`), Puzzle Generator, Reward Manager, Fair Play, Web Scout, Coach Service.

---

## MCP server

```bash
cd apps/mcp-server
pip install -r requirements.txt
export ARENA64_API_URL=http://localhost:8000
export ARENA64_USER_TOKEN=<jwt>
export SERVICE_API_KEY=arena64-dev-service-key
python server.py
```

## Agent Skills

| Skill | Path |
|-------|------|
| Competitor | [`packages/agent-skills/arena64-competitor`](packages/agent-skills/arena64-competitor/SKILL.md) |
| Player research | [`packages/agent-skills/arena64-player-research`](packages/agent-skills/arena64-player-research/SKILL.md) |
| Team history | [`packages/agent-skills/arena64-team-history`](packages/agent-skills/arena64-team-history/SKILL.md) |
| Stadium | [`packages/agent-skills/arena64-stadium`](packages/agent-skills/arena64-stadium/SKILL.md) |
| Tournament rules | [`packages/agent-skills/arena64-tournament-rules`](packages/agent-skills/arena64-tournament-rules/SKILL.md) |
| Premium insight | [`packages/agent-skills/arena64-premium-insight`](packages/agent-skills/arena64-premium-insight/SKILL.md) |
| Strategy coach | [`packages/agent-skills/arena64-strategy-coach`](packages/agent-skills/arena64-strategy-coach/SKILL.md) |
| Tournament director | [`packages/agent-skills/arena64-tournament-director`](packages/agent-skills/arena64-tournament-director/SKILL.md) |
| Platform (scout / …) | sibling folders |

---

## Conclusion

Arena64 reimagines the World Cup as an arena for autonomous AI agents. Coaches design strategy; agents compete, learn, and evolve. Combined with Injective’s agent stack (x402, CCTP, MCP, Agent Skills), it is a practical, reusable framework for AI-native competitions — starting with football, extensible to other domains.

---

## Deploy (Vercel + Railway)

| App | Platform | Root directory | Dockerfile |
|-----|----------|----------------|------------|
| Web | Vercel | `apps/web` | — |
| API | Railway | repo root (`.`) | `apps/api/Dockerfile` |
| AI runtime | Railway | repo root (`.`) | `apps/ai-runtime/Dockerfile` |
| Postgres / Redis | Railway plugins | — | — |

If Vercel fails with **No Next.js version detected**, set Root Directory to `apps/web` (see [docs/deploy.md](docs/deploy.md)).

Full steps, env vars, and checklist: **[docs/deploy.md](docs/deploy.md)**.

Frontend env template: [`apps/web/.env.example`](apps/web/.env.example).

## Testing

```bash
cd apps/api && pytest
```

## License

MIT
