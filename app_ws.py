import asyncio
import logging
from typing import Set

from fastapi import WebSocket

import metrics

logger = logging.getLogger(__name__)


class WebSocketManager:
    def __init__(self):
        self._connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)
            metrics.ACTIVE_WEBSOCKETS.set(len(self._connections))

    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            self._connections.discard(websocket)
            metrics.ACTIVE_WEBSOCKETS.set(len(self._connections))

    async def broadcast(self, message: dict):
        async with self._lock:
            snapshot = list(self._connections)
        results = await asyncio.gather(*[ws.send_json(message) for ws in snapshot], return_exceptions=True)
        dead = [ws for ws, r in zip(snapshot, results) if isinstance(r, Exception)]
        if dead:
            async with self._lock:
                for ws in dead:
                    self._connections.discard(ws)

    def count(self) -> int:
        return len(self._connections)


ws_manager = WebSocketManager()
