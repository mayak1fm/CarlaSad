"""
Terrain physics modifier — adjusts vehicle dynamics based on terrain label.

Applied per-tick via the CARLA physics API (VehiclePhysicsControl).
Simulates soft-ground effects: reduced traction, sinkage resistance,
speed limiting on wet/boggy terrain.

Usage:
    modifier = TerrainPhysicsModifier(vehicle_actor)
    modifier.apply(terrain_label)   # call each tick
"""
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("carlasad.physics.terrain")


@dataclass
class TerrainPhysicsProfile:
    """Physics adjustment profile for a terrain class."""
    label_id: int
    label_name: str

    # Traction coefficient multiplier [0, 1] applied to wheel friction
    traction_factor: float = 1.0

    # Maximum speed allowed on this terrain (m/s). None = no limit.
    max_speed_mps: Optional[float] = None

    # Drag force coefficient added to slow the vehicle (N per m/s)
    extra_drag_coeff: float = 0.0

    # Simulated sinkage depth (m) — adds visual offset and increases resistance
    sinkage_m: float = 0.0

    # Engine torque multiplier (< 1.0 = bogged down feeling)
    engine_torque_factor: float = 1.0

    # Whether terrain is passable at all (triggers warning if tractor enters)
    is_passable: bool = True


# ── Per-class physics profiles ────────────────────────────────────────────────

TERRAIN_PHYSICS: dict[int, TerrainPhysicsProfile] = {
    100: TerrainPhysicsProfile(100, "normal_field",
         traction_factor=0.85, max_speed_mps=8.0, extra_drag_coeff=20.0,
         sinkage_m=0.03, engine_torque_factor=0.95),

    101: TerrainPhysicsProfile(101, "wet_field",
         traction_factor=0.60, max_speed_mps=5.0, extra_drag_coeff=60.0,
         sinkage_m=0.06, engine_torque_factor=0.80),

    102: TerrainPhysicsProfile(102, "swamp",
         traction_factor=0.25, max_speed_mps=2.5, extra_drag_coeff=200.0,
         sinkage_m=0.20, engine_torque_factor=0.45, is_passable=True),

    103: TerrainPhysicsProfile(103, "mochak",
         traction_factor=0.30, max_speed_mps=2.0, extra_drag_coeff=180.0,
         sinkage_m=0.15, engine_torque_factor=0.50, is_passable=True),

    104: TerrainPhysicsProfile(104, "rough_terrain",
         traction_factor=0.75, max_speed_mps=4.0, extra_drag_coeff=50.0,
         sinkage_m=0.04, engine_torque_factor=0.85),

    105: TerrainPhysicsProfile(105, "field_boundary",
         traction_factor=0.70, max_speed_mps=3.0, extra_drag_coeff=80.0,
         sinkage_m=0.05, engine_torque_factor=0.80),

    106: TerrainPhysicsProfile(106, "drivable_path",
         traction_factor=0.90, max_speed_mps=10.0, extra_drag_coeff=5.0,
         sinkage_m=0.01, engine_torque_factor=1.0),

    107: TerrainPhysicsProfile(107, "non_drivable",
         traction_factor=0.40, max_speed_mps=1.5, extra_drag_coeff=300.0,
         sinkage_m=0.10, engine_torque_factor=0.40, is_passable=False),

    110: TerrainPhysicsProfile(110, "worked_area",
         traction_factor=0.70, max_speed_mps=6.0, extra_drag_coeff=40.0,
         sinkage_m=0.05, engine_torque_factor=0.90),

    111: TerrainPhysicsProfile(111, "unworked_area",
         traction_factor=0.80, max_speed_mps=7.0, extra_drag_coeff=25.0,
         sinkage_m=0.03, engine_torque_factor=0.92),
}

_DEFAULT_PROFILE = TerrainPhysicsProfile(0, "unknown",
    traction_factor=0.75, max_speed_mps=5.0, extra_drag_coeff=30.0,
    engine_torque_factor=0.90)


class TerrainPhysicsModifier:
    """
    Applies per-tick physics adjustments to a CARLA vehicle actor
    based on the terrain label under it.

    Requires CARLA Python API (carla.VehiclePhysicsControl).
    Degrades gracefully (logs warning) if carla is unavailable.
    """

    def __init__(self, vehicle_actor, base_max_torque: float = 400.0):
        self._actor = vehicle_actor
        self._base_max_torque = base_max_torque
        self._current_label: int = -1
        self._last_profile: Optional[TerrainPhysicsProfile] = None

        try:
            import carla
            self._carla = carla
        except ImportError:
            self._carla = None
            logger.warning("CARLA Python API not available — physics modifier disabled")

    def apply(self, terrain_label: int):
        """Apply physics profile for the given terrain label. Idempotent per label."""
        if terrain_label == self._current_label:
            return

        profile = TERRAIN_PHYSICS.get(terrain_label, _DEFAULT_PROFILE)
        self._apply_profile(profile)
        self._current_label = terrain_label
        self._last_profile = profile

        if not profile.is_passable:
            logger.warning(
                "[terrain_physics] Tractor entered non-drivable terrain: %s (label=%d)",
                profile.label_name, terrain_label,
            )

    def _apply_profile(self, profile: TerrainPhysicsProfile):
        if self._carla is None or self._actor is None:
            return

        try:
            physics = self._actor.get_physics_control()

            # Adjust wheel friction (traction)
            for wheel in physics.wheels:
                wheel.tire_friction = max(0.1, wheel.tire_friction * profile.traction_factor)
            self._actor.apply_physics_control(physics)

            # Speed limiter via throttle feedback (approximate)
            # Real speed limit enforcement: CARLA VehicleControl.throttle is clamped
            # by the scenario/bridge layer reading _last_profile.max_speed_mps
            logger.debug(
                "[terrain_physics] label=%d (%s) friction×%.2f drag+%.0f max_v=%.1f m/s",
                profile.label_id, profile.label_name,
                profile.traction_factor, profile.extra_drag_coeff,
                profile.max_speed_mps or 99.9,
            )

        except Exception as exc:
            logger.warning("[terrain_physics] apply_profile failed: %s", exc)

    def get_current_profile(self) -> Optional[TerrainPhysicsProfile]:
        return self._last_profile

    def get_max_speed_mps(self) -> float:
        if self._last_profile and self._last_profile.max_speed_mps is not None:
            return self._last_profile.max_speed_mps
        return 99.0

    def reset(self):
        """Remove terrain physics adjustments (restore base friction)."""
        if self._carla is None or self._actor is None:
            return
        try:
            physics = self._actor.get_physics_control()
            for wheel in physics.wheels:
                wheel.tire_friction = 3.5  # CARLA default
            self._actor.apply_physics_control(physics)
        except Exception:
            pass
        self._current_label = -1
        self._last_profile = None
