from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import init_db
from app.realtime.ws import router as ws_router
from app.routers import admin, agents, ai, auth, challenges, coach, faucet, insights, runtime, tournaments, trial, users, wallet, world_cup
from app.services.scout_worker import start_scout_scheduler, stop_scout_scheduler
from app.services.seed import seed_if_empty
from app.services.tournament_room_agent import start_room_agent, stop_room_agent
from app.services.world_cup_monitor_worker import start_world_cup_monitor, stop_world_cup_monitor


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await seed_if_empty()
    start_room_agent()
    start_scout_scheduler()
    start_world_cup_monitor()
    yield
    await stop_room_agent()
    await stop_scout_scheduler()
    await stop_world_cup_monitor()


settings = get_settings()
app = FastAPI(
    title="Arena64 API",
    description=(
        "AI Agent Arena for World Cup–inspired competitions — coaches deploy autonomous agents. "
        "Injective testnet: x402, CCTP, MCP, Agent Skills."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

# JWT auth uses Authorization headers (not cookies). Use wildcard origins with
# allow_credentials=False — the previous "*" + credentials=True combo is rejected
# by browsers and blocked MetaMask login from Vercel.
_cors_origins = list(settings.cors_origins)
for _o in ("http://localhost:3000", "http://127.0.0.1:3000"):
    if _o not in _cors_origins:
        _cors_origins.append(_o)
# Always allow any origin for this public API (Bearer tokens only).
if "*" not in _cors_origins:
    _cors_origins.append("*")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=r"https://.*\.(vercel\.app|railway\.app)",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(agents.router, prefix="/api")
app.include_router(runtime.router, prefix="/api")
app.include_router(wallet.router, prefix="/api")
app.include_router(faucet.router, prefix="/api")
app.include_router(tournaments.router, prefix="/api")
app.include_router(challenges.router, prefix="/api")
app.include_router(trial.router, prefix="/api")
app.include_router(world_cup.router, prefix="/api")
app.include_router(coach.router, prefix="/api")
app.include_router(insights.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(ai.router, prefix="/api")
app.include_router(ws_router)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "arena64-api",
        "product": "ai-agent-arena",
        "network": settings.injective_network,
        "chain_id": settings.injective_evm_chain_id,
        "usdc": settings.injective_usdc_address,
    }


@app.get("/")
async def root():
    return {
        "name": "Arena64",
        "tagline": "Coach your AI. Compete the Arena.",
        "docs": "/docs",
        "network": settings.injective_network,
        "injective": ["x402", "CCTP", "MCP", "Agent Skills"],
    }