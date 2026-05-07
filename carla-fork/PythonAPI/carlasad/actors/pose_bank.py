"""
Pose bank for dynamic actors — stores and replays time-indexed transform sequences.

Design:
  - Each actor class has a library of pre-recorded motion clips (YAML/JSON)
  - Clips are rigid-transform sequences: [(t_ms, x, y, z, yaw, pitch, roll), ...]
  - PoseBank.sample() draws a random clip and returns a pose interpolator
  - PoseInterpolator.get_transform(elapsed_ms) → (x, y, z, yaw)

Placement:
  - Clip origin (t=0) is placed at the spawn point
  - All subsequent poses are relative offsets from origin
  - Ensures the actor stays within the scene's placement bounds

Clips are stored as:
  object_bank/{class_name}/clips/{clip_id}.json
  {
    "class_name": "person",
    "duration_ms": 5000,
    "loop": true,
    "frames": [
      {"t_ms": 0,    "dx": 0.0, "dy": 0.0, "dz": 0.0, "yaw": 0.0},
      {"t_ms": 500,  "dx": 0.3, "dy": 0.0, "dz": 0.0, "yaw": 5.0},
      ...
    ]
  }
"""
import json
import math
import random
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger("carlasad.actors.pose_bank")

OBJECT_BANK_DIR = Path(__file__).parent.parent.parent.parent.parent / "gs-dataset-gen" / "object_bank"


class PoseFrame:
    __slots__ = ("t_ms", "dx", "dy", "dz", "yaw")

    def __init__(self, t_ms: float, dx: float, dy: float, dz: float, yaw: float):
        self.t_ms = t_ms
        self.dx   = dx
        self.dy   = dy
        self.dz   = dz
        self.yaw  = yaw


class PoseClip:
    def __init__(self, clip_id: str, frames: List[PoseFrame],
                 duration_ms: float, loop: bool = True):
        self.clip_id     = clip_id
        self.frames      = frames
        self.duration_ms = duration_ms
        self.loop        = loop

    @classmethod
    def from_dict(cls, data: dict) -> "PoseClip":
        frames = [
            PoseFrame(
                t_ms = float(f["t_ms"]),
                dx   = float(f.get("dx", 0.0)),
                dy   = float(f.get("dy", 0.0)),
                dz   = float(f.get("dz", 0.0)),
                yaw  = float(f.get("yaw", 0.0)),
            )
            for f in data.get("frames", [])
        ]
        frames.sort(key=lambda f: f.t_ms)
        return cls(
            clip_id     = data.get("clip_id", "unknown"),
            frames      = frames,
            duration_ms = float(data.get("duration_ms", frames[-1].t_ms if frames else 1000.0)),
            loop        = bool(data.get("loop", True)),
        )

    @classmethod
    def from_json(cls, path: Path) -> "PoseClip":
        return cls.from_dict(json.loads(path.read_text()))


class PoseInterpolator:
    """
    Interpolates between PoseFrames for smooth actor motion.

    Usage:
        interp = PoseInterpolator(clip, origin_x=10.0, origin_y=5.0, origin_yaw=45.0)
        x, y, z, yaw = interp.get_transform(elapsed_ms=1250)
    """

    def __init__(self, clip: PoseClip, origin_x: float, origin_y: float,
                 origin_z: float = 0.0, origin_yaw: float = 0.0):
        self._clip       = clip
        self._ox         = origin_x
        self._oy         = origin_y
        self._oz         = origin_z
        self._oyaw_rad   = math.radians(origin_yaw)

    def get_transform(self, elapsed_ms: float):
        """Returns (world_x, world_y, world_z, world_yaw_deg)."""
        clip = self._clip
        if not clip.frames:
            return self._ox, self._oy, self._oz, math.degrees(self._oyaw_rad)

        t = elapsed_ms
        if clip.loop and clip.duration_ms > 0:
            t = t % clip.duration_ms

        # Find surrounding keyframes
        frames = clip.frames
        if t <= frames[0].t_ms:
            f = frames[0]
            dx, dy, dz, dyaw = f.dx, f.dy, f.dz, f.yaw
        elif t >= frames[-1].t_ms:
            f = frames[-1]
            dx, dy, dz, dyaw = f.dx, f.dy, f.dz, f.yaw
        else:
            # Binary search
            lo, hi = 0, len(frames) - 1
            while hi - lo > 1:
                mid = (lo + hi) // 2
                if frames[mid].t_ms <= t:
                    lo = mid
                else:
                    hi = mid
            a, b = frames[lo], frames[hi]
            alpha = (t - a.t_ms) / max(b.t_ms - a.t_ms, 1e-6)
            dx   = a.dx   + alpha * (b.dx   - a.dx)
            dy   = a.dy   + alpha * (b.dy   - a.dy)
            dz   = a.dz   + alpha * (b.dz   - a.dz)
            dyaw = a.yaw  + alpha * (b.yaw  - a.yaw)

        # Rotate relative offset by origin yaw
        cos_o = math.cos(self._oyaw_rad)
        sin_o = math.sin(self._oyaw_rad)
        wx = self._ox + cos_o * dx - sin_o * dy
        wy = self._oy + sin_o * dx + cos_o * dy
        wz = self._oz + dz
        wyaw = math.degrees(self._oyaw_rad) + dyaw

        return wx, wy, wz, wyaw


class PoseBank:
    """
    Loads and caches motion clips for a given actor class.
    Falls back to procedural motion if no clips are on disk.
    """

    def __init__(self, class_name: str, rng: Optional[random.Random] = None):
        self._class_name = class_name
        self._rng        = rng or random.Random(42)
        self._clips: List[PoseClip] = []
        self._load_clips()

    def _load_clips(self):
        clips_dir = OBJECT_BANK_DIR / self._class_name / "clips"
        if not clips_dir.exists():
            logger.debug("[pose_bank] No clips dir for %s — using procedural fallback",
                         self._class_name)
            return

        for clip_path in clips_dir.glob("*.json"):
            try:
                clip = PoseClip.from_json(clip_path)
                self._clips.append(clip)
            except Exception as exc:
                logger.warning("[pose_bank] Failed to load %s: %s", clip_path, exc)

        logger.info("[pose_bank] Loaded %d clips for %s", len(self._clips), self._class_name)

    def sample(self, seed: Optional[int] = None) -> PoseClip:
        """Return a random clip, or a procedural one if no clips loaded."""
        if self._clips:
            rng = random.Random(seed) if seed is not None else self._rng
            return rng.choice(self._clips)
        return self._make_procedural_clip(seed)

    def _make_procedural_clip(self, seed: Optional[int]) -> PoseClip:
        """Generate a simple wandering motion clip procedurally."""
        rng = random.Random(seed if seed is not None else 0)
        frames: List[PoseFrame] = []
        t = 0.0
        dx = dy = 0.0

        speed_mps  = 0.8 if self._class_name == "person" else 0.2
        duration_s = 8.0
        step_ms    = 500.0
        direction  = rng.uniform(0, 360)

        while t <= duration_s * 1000:
            if rng.random() < 0.15:  # 15% chance to change direction
                direction += rng.uniform(-60, 60)
            rad  = math.radians(direction)
            step = speed_mps * (step_ms / 1000.0)
            dx  += math.cos(rad) * step
            dy  += math.sin(rad) * step
            frames.append(PoseFrame(t_ms=t, dx=dx, dy=dy, dz=0.0, yaw=direction))
            t += step_ms

        return PoseClip(
            clip_id     = f"procedural_{self._class_name}_{seed}",
            frames      = frames,
            duration_ms = t,
            loop        = True,
        )

    def make_interpolator(self, origin_x: float, origin_y: float,
                          origin_z: float = 0.0, origin_yaw: float = 0.0,
                          seed: Optional[int] = None) -> PoseInterpolator:
        clip = self.sample(seed)
        return PoseInterpolator(clip, origin_x, origin_y, origin_z, origin_yaw)
