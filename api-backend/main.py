"""CarlaSad Operator API."""
import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from carla_client import carla_client
from routers import mission, world, recording, sessions, scenario, sim
from ws import state_websocket_endpoint, events_websocket_endpoint

logging.basicConfig(
    level=logging.DEBUG if os.environ.get("DEBUG") else logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("carlasad.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Attempt CARLA connection on startup (non-fatal if unavailable)
    connected = await carla_client.connect()
    if connected:
        logger.info("CARLA connection established on startup")
    else:
        logger.warning("CARLA not reachable on startup — will retry on first request")
    yield
    logger.info("API shutdown")


app = FastAPI(
    title="CarlaSad Operator API",
    description="Operator API for CarlaSad autonomous tractor simulation platform",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# REST routers
app.include_router(mission.router,    prefix="/api/v1/mission",    tags=["Mission"])
app.include_router(world.router,      prefix="/api/v1/world",      tags=["World"])
app.include_router(recording.router,  prefix="/api/v1/recording",  tags=["Recording"])
app.include_router(sessions.router,   prefix="/api/v1/sessions",   tags=["Sessions"])
app.include_router(scenario.router,   prefix="/api/v1/scenario",   tags=["Scenario"])
app.include_router(sim.router,        prefix="/api/v1/sim",        tags=["Simulation"])

# WebSocket endpoints
@app.websocket("/ws/state")
async def ws_state(ws: WebSocket):
    await state_websocket_endpoint(ws)

@app.websocket("/ws/events")
async def ws_events(ws: WebSocket):
    await events_websocket_endpoint(ws)

# Utility
@app.get("/health")
def health():
    return {
        "ok": True,
        "service": "carlasad-api",
        "carla_connected": carla_client.is_connected(),
    }

@app.get("/api/v1/carla/status")
async def carla_status():
    await carla_client.ensure_connected()
    return carla_client.get_status()

@app.get("/api/v1/sensor_rigs")
def list_sensor_rigs():
    return [
        {
            "id": "default",
            "cameras": 6, "camera_names": ["front", "rear", "left", "right", "front_left", "front_right"],
            "lidars": 2,  "lidar_names": ["front", "top"],
            "has_radar": True, "has_thermal": True, "has_gnss": True, "has_imu": True,
        },
        {
            "id": "minimal",
            "cameras": 1, "camera_names": ["front"],
            "lidars": 1,  "lidar_names": ["front"],
            "has_radar": False, "has_thermal": False, "has_gnss": True, "has_imu": True,
        },
    ]
