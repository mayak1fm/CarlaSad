"""
WebSocket endpoint: /ws/events
Pushes MissionEvent immediately on occurrence (not polled).
"""
import asyncio
import json
import logging
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("carlasad.ws.events")


class EventConnectionManager:
    def __init__(self):
        self._connections: set[WebSocket] = set()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._connections.add(ws)

    def disconnect(self, ws: WebSocket):
        self._connections.discard(ws)

    async def push_event(self, event: dict):
        if not self._connections:
            return
        payload = json.dumps(event)
        dead = set()
        for ws in self._connections:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.add(ws)
        self._connections -= dead


events_manager = EventConnectionManager()


async def events_websocket_endpoint(ws: WebSocket):
    await events_manager.connect(ws)
    try:
        # Send welcome frame
        await ws.send_text(json.dumps({"type": "connected", "channel": "events"}))
        # Hold connection open; events are pushed externally via events_manager.push_event()
        while True:
            try:
                # Echo keep-alive pings from client
                data = await asyncio.wait_for(ws.receive_text(), timeout=30.0)
                if data == "ping":
                    await ws.send_text(json.dumps({"type": "pong"}))
            except asyncio.TimeoutError:
                # Send server-side keepalive
                await ws.send_text(json.dumps({"type": "keepalive"}))
            except WebSocketDisconnect:
                break
    except WebSocketDisconnect:
        pass
    finally:
        events_manager.disconnect(ws)
