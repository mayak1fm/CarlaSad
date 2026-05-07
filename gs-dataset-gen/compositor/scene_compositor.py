"""
Scene compositor for GS synthetic dataset.

Pipeline:
  load_scene → place_objects → validate_placement → apply_relighting → render_passes

Rules (from CLAUDE.md — NEVER violate):
  ✅ Static background GS + separate object assets
  ✅ Labels from passes (NOT from final RGB)
  ✅ Shadow pass uses proxy mesh (NOT natural RGB shadows)
  ✅ Post-insertion relighting (D3DR-style)
  ✅ Proxy geometry for collision + placement checks
  ✅ Seed-based reproducibility
  ❌ No giant monolithic dynamic GS scene
  ❌ No labels from final RGB
  ❌ No raw splats as collision model
"""
import random
import yaml
import numpy as np
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field

from .lighting_adapter import LightingAdapter, SceneLighting
from .shadow_compositor import ProxyMeshShadow

SCENE_LIBRARY_DIR = Path(__file__).parent.parent / "scene_library"
OBJECT_BANK_DIR   = Path(__file__).parent.parent / "object_bank"


@dataclass
class PlacedObject:
    class_name: str
    class_id: int
    instance_id: str
    transform: dict                      # {x, y, z, yaw}
    asset_meta: dict
    proxy_bbox: Optional[list] = None    # [[cx,cy,cz],[sx,sy,sz],[rx,ry,rz]]
    support_polygon: Optional[list] = None
    rendered_rgba: Optional[np.ndarray] = None  # H x W x 4
    relit: bool = False
    shadow_applied: bool = False


class SceneCompositor:
    def __init__(self, seed: int = 42, image_size: Tuple[int, int] = (1080, 1920)):
        self._seed = seed
        self._rng  = random.Random(seed)
        self._image_size = image_size     # (H, W)

        self._scene_name: Optional[str] = None
        self._scene_meta: Optional[dict] = None
        self._scene_rgb: Optional[np.ndarray] = None   # background render H x W x 3
        self._placed_objects: List[PlacedObject] = []

        self._lighting_adapter: Optional[LightingAdapter] = None
        self._shadow_compositor: Optional[ProxyMeshShadow] = None
        self._object_bank_cache: Dict[str, dict] = {}

    # ── Scene Loading ──────────────────────────────────────────────────────

    def load_scene(self, scene_name: str):
        scene_path = SCENE_LIBRARY_DIR / scene_name
        meta_path  = scene_path / "metadata.yaml"
        if not meta_path.exists():
            raise FileNotFoundError(
                f"Scene '{scene_name}' not found. "
                f"Available: {[d.name for d in SCENE_LIBRARY_DIR.iterdir() if d.is_dir()]}"
            )
        with open(meta_path) as f:
            self._scene_meta = yaml.safe_load(f)

        self._scene_name = scene_name
        weather = self._scene_meta.get("weather_preset", "ClearNoon")
        lighting = SceneLighting.from_weather_preset(weather)
        self._lighting_adapter = LightingAdapter(lighting)
        self._shadow_compositor = ProxyMeshShadow(lighting)

        # Load background render if available
        self._scene_rgb = self._load_background_render(scene_path)

    def reset(self, seed: int):
        self._rng = random.Random(seed)
        self._placed_objects = []

    # ── Object Placement ───────────────────────────────────────────────────

    def place_object(self, class_name: str, seed: Optional[int] = None) -> Optional[PlacedObject]:
        """
        Place an object using proxy geometry for collision/terrain checks.
        Placement validated via proxy bbox, NOT raw splats.
        """
        rng = random.Random(seed) if seed is not None else self._rng
        asset_meta = self._load_object_meta(class_name)
        if asset_meta is None:
            return None

        bounds = self._scene_meta.get("placement_bounds", {})
        allowed_classes = self._scene_meta.get("valid_object_classes", [class_name])
        if class_name not in allowed_classes:
            return None

        transform = self._sample_valid_placement(class_name, asset_meta, bounds, rng)
        if transform is None:
            return None

        bbox = asset_meta.get("oriented_bbox")
        proxy_bbox = None
        if bbox:
            proxy_bbox = [
                [bbox["center"]["x"] if isinstance(bbox["center"], dict) else bbox["center"][0],
                 bbox["center"]["y"] if isinstance(bbox["center"], dict) else bbox["center"][1],
                 bbox["center"]["z"] if isinstance(bbox["center"], dict) else bbox["center"][2]],
                [bbox["size"]["x"] if isinstance(bbox["size"], dict) else bbox["size"][0],
                 bbox["size"]["y"] if isinstance(bbox["size"], dict) else bbox["size"][1],
                 bbox["size"]["z"] if isinstance(bbox["size"], dict) else bbox["size"][2]],
                [0.0, 0.0, transform["yaw"]],
            ]

        obj = PlacedObject(
            class_name=class_name,
            class_id=asset_meta.get("class_id", 99),
            instance_id=f"{class_name}_{len(self._placed_objects):04d}_{seed or 0}",
            transform=transform,
            asset_meta=asset_meta,
            proxy_bbox=proxy_bbox,
            support_polygon=asset_meta.get("support_polygon"),
        )
        self._placed_objects.append(obj)
        return obj

    def validate_placement(self):
        """Remove objects that violate placement constraints (proxy geometry checks)."""
        valid: List[PlacedObject] = []
        for obj in self._placed_objects:
            if (self._check_no_floating(obj) and
                self._check_no_sinking(obj) and
                self._check_no_intersection(obj, valid)):
                valid.append(obj)
            # else: silently drop — compositor never hard-errors on placement
        removed = len(self._placed_objects) - len(valid)
        if removed > 0:
            print(f"[Compositor] Removed {removed} invalid placements")
        self._placed_objects = valid

    # ── Rendering ──────────────────────────────────────────────────────────

    def apply_relighting(self):
        """Post-insertion lighting adaptation (D3DR-style)."""
        if self._lighting_adapter is None:
            return
        for obj in self._placed_objects:
            if obj.rendered_rgba is not None:
                obj.rendered_rgba = self._lighting_adapter.relight_object(
                    object_rgba=obj.rendered_rgba,
                )
            obj.relit = True

    def render_passes(
        self,
        rgb: bool = True,
        object_id: bool = True,
        semantic: bool = True,
        depth: bool = True,
        shadow: bool = True,
    ) -> dict:
        """
        Render all passes for label generation.
        Labels MUST come from these passes, not from final RGB.
        Shadow pass uses proxy mesh, not natural RGB.
        """
        H, W = self._image_size
        passes = {}

        if rgb:
            bg = self._scene_rgb.copy() if self._scene_rgb is not None else np.zeros((H, W, 3), np.float32)
            if shadow and self._shadow_compositor:
                bg = self._apply_shadows_to_background(bg)
            passes["rgb"] = self._composite_rgb(bg)

        if object_id:
            passes["object_id"] = self._render_object_id_pass(H, W)

        if semantic:
            passes["semantic"] = self._render_semantic_pass(H, W)

        if depth:
            passes["depth"] = self._render_depth_pass(H, W)

        return passes

    def get_object_states(self) -> List[dict]:
        return [
            {
                "class_name":  obj.class_name,
                "class_id":    obj.class_id,
                "instance_id": obj.instance_id,
                "transform":   obj.transform,
                "proxy_bbox":  obj.proxy_bbox,
                "support_polygon": obj.support_polygon,
                "relit":       obj.relit,
            }
            for obj in self._placed_objects
        ]

    # ── Placement Validation ───────────────────────────────────────────────

    def _check_no_floating(self, obj: PlacedObject) -> bool:
        """Object must not float above terrain."""
        # With terrain snap enabled, z should equal terrain height
        # For flat terrain: z should be 0.0
        if not obj.asset_meta.get("placement_rules", {}).get("terrain_snap", True):
            return True
        return abs(obj.transform.get("z", 0.0)) < 0.5

    def _check_no_sinking(self, obj: PlacedObject) -> bool:
        """Object must not be buried below terrain (unless allowed)."""
        rules = obj.asset_meta.get("placement_rules", {})
        if rules.get("allow_partial_burial"):
            burial_max = rules.get("burial_fraction", [0, 0.3])[1]
            if obj.proxy_bbox:
                height = obj.proxy_bbox[1][2]
                return obj.transform.get("z", 0.0) > -(height * burial_max)
        return obj.transform.get("z", 0.0) >= -0.1

    def _check_no_intersection(self, obj: PlacedObject, existing: List[PlacedObject]) -> bool:
        """Check proxy bbox intersection against all existing objects."""
        if obj.proxy_bbox is None:
            return True
        ox, oy = obj.transform["x"], obj.transform["y"]
        os = obj.proxy_bbox[1]
        clearance = obj.asset_meta.get("placement_rules", {}).get("min_clearance_m", 0.5)

        for other in existing:
            if other.proxy_bbox is None:
                continue
            ex, ey = other.transform["x"], other.transform["y"]
            es = other.proxy_bbox[1]
            dx = abs(ox - ex)
            dy = abs(oy - ey)
            min_dx = (os[0] + es[0]) / 2 + clearance
            min_dy = (os[1] + es[1]) / 2 + clearance
            if dx < min_dx and dy < min_dy:
                return False
        return True

    # ── Rendering Internals ────────────────────────────────────────────────

    def _apply_shadows_to_background(self, background_rgb: np.ndarray) -> np.ndarray:
        H, W = background_rgb.shape[:2]
        for obj in self._placed_objects:
            shadow_mask = self._shadow_compositor.compute_shadow_mask(
                image_size=(H, W),
                proxy_bbox=obj.proxy_bbox,
                object_transform=obj.transform,
                terrain_height=0.0,
            )
            background_rgb = self._shadow_compositor.apply_to_image(
                background_rgb.astype(np.float32) / 255.0 if background_rgb.max() > 1.0 else background_rgb,
                shadow_mask,
            )
            background_rgb = (background_rgb * 255).clip(0, 255).astype(np.uint8) if background_rgb.max() <= 1.0 else background_rgb
            obj.shadow_applied = True
        return background_rgb

    def _composite_rgb(self, background: np.ndarray) -> np.ndarray:
        """Composite all placed objects over background."""
        result = background.copy()
        for obj in self._placed_objects:
            if obj.rendered_rgba is None:
                continue
            H, W = result.shape[:2]
            # TODO: project object onto image plane and alpha-composite
            # For now: background is returned unchanged (renderer not yet implemented)
        return result

    def _render_object_id_pass(self, H: int, W: int) -> np.ndarray:
        """
        Per-object ID image. Each object gets a unique color.
        Labels come from this pass, NOT from RGB.
        Background = 0.
        """
        id_map = np.zeros((H, W, 3), dtype=np.uint8)
        for i, obj in enumerate(self._placed_objects):
            color_id = i + 1  # 0 = background
            r = (color_id & 0xFF0000) >> 16
            g = (color_id & 0x00FF00) >> 8
            b = (color_id & 0x0000FF)
            # TODO: rasterize proxy bbox silhouette in image space
            _ = (r, g, b)  # placeholder
        return id_map

    def _render_semantic_pass(self, H: int, W: int) -> np.ndarray:
        """Semantic label ID image. Each class gets its class_id color."""
        sem_map = np.zeros((H, W), dtype=np.uint8)
        # TODO: rasterize each object's class_id using proxy bbox
        return sem_map

    def _render_depth_pass(self, H: int, W: int) -> np.ndarray:
        """Depth image (meters). Background = far plane (1000m)."""
        depth_map = np.full((H, W), 1000.0, dtype=np.float32)
        # TODO: render depth from GS + project proxy bbox near depths
        return depth_map

    # ── Asset Loading ──────────────────────────────────────────────────────

    def _load_object_meta(self, class_name: str) -> Optional[dict]:
        if class_name in self._object_bank_cache:
            return self._object_bank_cache[class_name]
        meta_path = OBJECT_BANK_DIR / class_name / "metadata.yaml"
        if not meta_path.exists():
            print(f"[Compositor] No metadata for '{class_name}' at {meta_path}")
            return None
        with open(meta_path) as f:
            meta = yaml.safe_load(f)
        self._object_bank_cache[class_name] = meta
        return meta

    def _load_background_render(self, scene_path: Path) -> Optional[np.ndarray]:
        """Load pre-rendered background or return None (will be rendered on demand)."""
        for ext in ["background.png", "background.jpg"]:
            p = scene_path / ext
            if p.exists():
                try:
                    import cv2
                    img = cv2.imread(str(p))
                    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                except ImportError:
                    pass
        return None

    def _sample_valid_placement(
        self,
        class_name: str,
        asset_meta: dict,
        bounds: dict,
        rng: random.Random,
    ) -> Optional[dict]:
        """Sample a valid placement position respecting terrain and bounds."""
        x_min = bounds.get("x_min", -50.0)
        x_max = bounds.get("x_max",  50.0)
        y_min = bounds.get("y_min", -50.0)
        y_max = bounds.get("y_max",  50.0)

        for _ in range(50):   # max attempts
            x = rng.uniform(x_min, x_max)
            y = rng.uniform(y_min, y_max)
            z = 0.0           # terrain snap (flat terrain default)
            yaw = rng.uniform(0, 360)

            # Scale variation
            rules = asset_meta.get("scale_variations", {})
            if rules:
                s = rng.uniform(
                    rules.get("min_scale", 1.0),
                    rules.get("max_scale", 1.0),
                )
            else:
                s = 1.0

            transform = {"x": x, "y": y, "z": z, "yaw": yaw, "scale": s}

            # Quick bounds check only; full proxy check is in validate_placement
            if x_min <= x <= x_max and y_min <= y <= y_max:
                return transform

        return None
