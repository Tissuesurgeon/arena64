# Deploy Arena64 (Vercel + Railway)

Target split:

| Service | Platform | Root directory | Dockerfile |
|---------|----------|----------------|------------|
| Web (`apps/web`) | **Vercel** | `apps/web` | — (Next.js) |
| API (`apps/api`) | **Railway** | **`.`** (repo root) | `apps/api/Dockerfile` |
| AI runtime (`apps/ai-runtime`) | **Railway** | **`.`** (repo root) | `apps/ai-runtime/Dockerfile` |
| Postgres + Redis | **Railway** plugins | — | — |
| MCP server (optional) | **Railway** | `apps/mcp-server` | `Dockerfile` |
| Contracts | On-chain (Foundry) | `blockchain/` | — |

> **API build tip:** Do **not** set Railway Root Directory to `apps/api`. The Dockerfile copies `apps/api/app`, so the build context must be the monorepo root. Wrong context causes: `"/app": not found`.

---

## 1. Railway — Postgres & Redis

1. Create a Railway project (e.g. `arena64`).
2. Add **PostgreSQL** and **Redis** plugins.
3. Note the generated `DATABASE_URL` / `REDIS_URL` (or use variable references).

The API normalizes `postgres://` / `postgresql://` to `postgresql+asyncpg://` automatically. You do **not** need a separate `DATABASE_URL_SYNC` if you only set `DATABASE_URL`.

---

## 2. Railway — API

1. New service → Deploy from GitHub.
2. Settings → Build:
   - **Root Directory** = empty / `.` (repository root)
   - **Dockerfile path** = `apps/api/Dockerfile`
   - Optional config path = `apps/api/railway.toml`
3. Variables (minimum):

| Variable | Value |
|----------|--------|
| `DATABASE_URL` | Reference from Postgres (`${{Postgres.DATABASE_URL}}`) |
| `REDIS_URL` | Reference from Redis |
| `SECRET_KEY` | Long random secret |
| `SERVICE_API_KEY` | Shared with AI runtime |
| `API_CORS_ORIGINS` | `https://your-app.vercel.app` (comma-separated if multiple) |
| `APP_ENV` | `production` |
| `INJECTIVE_NETWORK` | `testnet` (until mainnet checklist) |

Optional product vars: `ARENA64_TREASURY_ADDRESS`, `ARENA64_TREASURY_PRIVATE_KEY`, `INJ_KEY_EVM`, `INJ_FAUCET_ADDRESS`, `QWEN_API_KEY` / `DASHSCOPE_API_KEY`, `AI_PROVIDER=qwen` (cloud) or `rules` (no LLM).

4. Confirm `GET /health` returns `"status":"ok"`.

---

## 3. Railway — AI runtime

Cups need this worker; without it agents do not answer live challenges.

1. New service → **Root Directory = `.`** (monorepo root).
2. Dockerfile path: `apps/ai-runtime/Dockerfile` (see `apps/ai-runtime/railway.toml`).
3. Variables:

| Variable | Value |
|----------|--------|
| `ARENA64_API_URL` | Public Railway API URL, e.g. `https://….up.railway.app` |
| `SERVICE_API_KEY` | **Same** as API |
| `RUNTIME_POLL_SECONDS` | `2.5` |
| `RUNTIME_LLM_ENABLED` | `true` if using Qwen/Ollama; else `false` |
| `RUNTIME_WORKER_ID` | `0` |

The image bakes in `packages/agent-skills` → `/agent-skills` and `packages/prompts` → `/agent-prompts`.

---

## 4. Vercel — Web

### Preferred setup (Root Directory)

1. Import the repo in Vercel.
2. **Settings → General → Root Directory → `apps/web`** (Edit → select `apps/web`).
3. Framework: **Next.js**.
4. Environment variables — copy from `apps/web/.env.example`:

| Variable | Example |
|----------|---------|
| `NEXT_PUBLIC_API_URL` | `https://your-api.up.railway.app` |
| `NEXT_PUBLIC_WS_URL` | `wss://your-api.up.railway.app/ws` |
| `NEXT_PUBLIC_CHAIN_ID` | `1439` |
| `NEXT_PUBLIC_CHAIN_NAME` | `Injective EVM Testnet` |
| `NEXT_PUBLIC_RPC_URL` | Injective testnet RPC |
| `NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID` | optional |

5. Redeploy after setting env (Next inlines `NEXT_PUBLIC_*` at build time).
6. Put the Vercel URL into Railway API `API_CORS_ORIGINS` and redeploy API if needed.

### If you see: `No Next.js version detected`

Vercel is building the **monorepo root** (root `package.json` has no app `src/`). Fix:

1. Project → **Settings → General → Root Directory** → set to **`apps/web`**
2. Save → **Deployments → Redeploy**

The repo also includes a root `vercel.json` fallback that builds `apps/web` when Root Directory is left empty, but **`apps/web` as Root Directory is still preferred**.

---

## 5. Optional — MCP on Railway

Root Directory = `apps/mcp-server`. Set `ARENA64_API_URL` + `SERVICE_API_KEY`. Most demos run MCP locally against the deployed API instead.

---

## Checklist

- [ ] Postgres + Redis on Railway
- [ ] API `/health` green
- [ ] AI runtime connected (`ARENA64_API_URL` + matching `SERVICE_API_KEY`)
- [ ] Vercel root = `apps/web` with production `NEXT_PUBLIC_*`
- [ ] `API_CORS_ORIGINS` includes Vercel URL
- [ ] Treasury / faucet keys set if testing deposits and INJ claims
- [ ] Never put `INJ_KEY_EVM` or treasury private keys in Vercel
