"""CarlaSad Operator API — entry point."""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import mission, world, recording, sessions, scenario

app = FastAPI(
    title="CarlaSad Operator API",
    description="Operator API for CarlaSad tractor simulation platform",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(mission.router, prefix="/api/v1/mission", tags=["Mission"])
app.include_router(world.router, prefix="/api/v1/world", tags=["World"])
app.include_router(recording.router, prefix="/api/v1/recording", tags=["Recording"])
app.include_router(sessions.router, prefix="/api/v1/sessions", tags=["Sessions"])
app.include_router(scenario.router, prefix="/api/v1/scenario", tags=["Scenario"])


@app.get("/health")
def health():
    return {"ok": True, "service": "carlasad-api"}


@app.get("/api/v1/sensor_rigs")
def list_sensor_rigs():
    return [
        {"id": "default", "cameras": 6, "lidars": 2, "has_thermal": True, "has_radar": True},
        {"id": "minimal", "cameras": 1, "lidars": 1, "has_thermal": False, "has_radar": False},
    ]
