# Deploy Arena64 (Vercel + Railway)

Target split:

| Service | Platform | Root directory | Dockerfile |
|---------|----------|----------------|------------|
| Web (`apps/web`) | **Vercel** | **`apps/web`** | — (Next.js) |
| **Backend** (API + AI runtime) | **Railway** | **`.`** (repo root) | **`Dockerfile`** |
| Postgres + Redis | **Railway** plugins | — | — |
| MCP server (optional) | Local / separate Railway | `apps/mcp-server` | `Dockerfile` |
| Contracts | On-chain (Foundry) | `blockchain/` | — |

The root **`Dockerfile`** runs **both**:

1. **API** (`uvicorn` on `$PORT`) — tournaments, wallet, scout, room agent  
2. **AI runtime** (`apps/ai-runtime`) — autonomous agent answers during cups  

Skills/prompts are baked in (`/agent-skills`, `/agent-prompts`). Without the runtime process, cups stay empty of agent play.

> **Build tip:** Root Directory must be the **repository root**. Wrong context causes missing `apps/…` COPY paths.

---

## 1. Railway — Postgres & Redis

1. Create a Railway project (e.g. `arena64`).
2. Add **PostgreSQL** and **Redis** plugins.
3. Reference `DATABASE_URL` / `REDIS_URL` on the backend service.

The API normalizes `postgres://` / `postgresql://` to `postgresql+asyncpg://` automatically. You do **not** need `DATABASE_URL_SYNC` if you only set `DATABASE_URL`.

---

## 2. Railway — Backend (API + AI runtime)

1. New service → Deploy from GitHub.
2. Settings → Build:
   - **Root Directory** = empty / `.` (repository root)
   - **Dockerfile path** = `Dockerfile` (repo root — **not** `apps/api/Dockerfile`)
   - Config file = `railway.toml`
3. Variables (minimum):

| Variable | Value |
|----------|--------|
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` |
| `REDIS_URL` | Redis plugin URL |
| `SECRET_KEY` | Long random secret |
| `SERVICE_API_KEY` | Shared secret (runtime uses the same) |
| `API_CORS_ORIGINS` | `https://your-app.vercel.app` |
| `APP_ENV` | `production` |
| `INJECTIVE_NETWORK` | `testnet` |

Optional: `ARENA64_TREASURY_ADDRESS`, `ARENA64_TREASURY_PRIVATE_KEY`, `INJ_KEY_EVM`, `INJ_FAUCET_ADDRESS`, `QWEN_API_KEY` / `DASHSCOPE_API_KEY`, `AI_PROVIDER=qwen` or `rules`, `RUNTIME_LLM_ENABLED=true`, `RUNTIME_POLL_SECONDS=2.5`.

`ARENA64_API_URL` defaults to `http://127.0.0.1:$PORT` inside the container (runtime → local API). Override only if you split services.

4. Confirm `GET /health` returns `"status":"ok"`.
5. Confirm runtime logs mention `Arena64 competition runtime` and skills loaded.

### Advanced: split API and runtime

Use `apps/api/Dockerfile` + `apps/ai-runtime/Dockerfile` as **two** Railway services. Set the runtime’s `ARENA64_API_URL` to the API’s public URL and the same `SERVICE_API_KEY`. Prefer the single root `Dockerfile` for hackathon deploys.

---

## 3. Vercel — Web

### Preferred setup (Root Directory)

1. Import the repo in Vercel.
2. **Settings → General → Root Directory → `apps/web`**.
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
6. Put the Vercel URL into Railway `API_CORS_ORIGINS` and redeploy the backend if needed.

### If you see: `No Next.js version detected`

1. Project → **Settings → General → Root Directory** → **`apps/web`**
2. Save → **Deployments → Redeploy**

---

## 4. Optional — MCP

Run locally against the deployed API, or deploy `apps/mcp-server` separately. Not included in the root backend image (stdio sidecar).

---

## Checklist

- [ ] Postgres + Redis on Railway
- [ ] Backend uses root **`Dockerfile`** (API + AI runtime)
- [ ] `/health` green; runtime logs show skills
- [ ] Vercel root = `apps/web` with production `NEXT_PUBLIC_*`
- [ ] `API_CORS_ORIGINS` includes Vercel URL
- [ ] Treasury / faucet keys set if testing deposits and INJ claims
- [ ] Never put `INJ_KEY_EVM` or treasury private keys in Vercel
