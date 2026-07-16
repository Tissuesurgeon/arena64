from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect


class ConnectionManager:
    def __init__(self) -> None:
        self.rooms: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, room: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self.rooms[room].add(websocket)

    async def disconnect(self, room: str, websocket: WebSocket) -> None:
        async with self._lock:
            self.rooms[room].discard(websocket)

    async def broadcast(self, room: str, payload: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        for ws in list(self.rooms.get(room, set())):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(room, ws)


manager = ConnectionManager()
router = APIRouter()


@router.websocket("/ws/tournaments/{tournament_id}")
async def tournament_ws(websocket: WebSocket, tournament_id: str) -> None:
    room = f"tournament:{tournament_id}"
    await manager.connect(room, websocket)
    try:
        await websocket.send_json({"type": "connected", "tournament_id": tournament_id})
        while True:
            data = await websocket.receive_json()
            # Clients may ping or send fair-play focus events via WS
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        await manager.disconnect(room, websocket)


async def emit_tournament(tournament_id: str, event_type: str, data: dict | None = None) -> None:
    await manager.broadcast(
        f"tournament:{tournament_id}",
        {"type": event_type, "data": data or {}},
    )