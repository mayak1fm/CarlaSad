"""
WebSocket endpoint: /ws/state
Streams MissionStatus at 10Hz while mission is active, 1Hz otherwise.
"""
import asyncio
import json
import time
import logging
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("carlasad.ws.state")


class StateConnectionManager:
    def __init__(self):
        self._connections: set[WebSocket] = set()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._connections.add(ws)
        logger.info("WS state client connected, total: %d", len(self._connections))

    def disconnect(self, ws: WebSocket):
        self._connections.discard(ws)
        logger.info("WS state client disconnected, total: %d", len(self._connections))

    async def broadcast(self, data: dict):
        if not self._connections:
            return
        payload = json.dumps(data)
        dead = set()
        for ws in self._connections:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.add(ws)
        self._connections -= dead


state_manager = StateConnectionManager()


async def state_websocket_endpoint(ws: WebSocket):
    from carla_client import carla_client
    from models.mission import get_active_mission
    from sim_controller import sim_controller

    await state_manager.connect(ws)
    try:
        while True:
            mission = get_active_mission()
            interval = 0.1 if mission.state == "running" else 1.0

            payload = {
                "ts": time.time(),
                "mission": mission.model_dump(),
                "carla": carla_client.get_status(),
                "ego_pose": sim_controller.get_ego_pose(),
            }
            try:
                await ws.send_text(json.dumps(payload))
            except WebSocketDisconnect:
                break
            except Exception:
                break
            await asyncio.sleep(interval)
    except WebSocketDisconnect:
        pass
    finally:
        state_manager.disconnect(ws)
