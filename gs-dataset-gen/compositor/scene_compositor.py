"""
Scene compositor for GS synthetic dataset generation.

Pipeline:
    load_scene → place_objects → validate_placement → apply_relighting → render_passes

Key rules:
- Static background = static GS scene
- Dynamic objects = separate assets with proxy geometry
- Labels from passes (NOT from final RGB)
- Shadow pass uses proxy mesh (NOT natural RGB shadows)
- Relighting is post-insertion (D3DR-style)
- Placement validated via proxy geometry (NOT raw splats)
"""
import random
from pathlib import Path
from typing import Dict, Any, List, Optional

SCENE_LIBRARY_DIR = Path(__file__).parent.parent / "scene_library"
OBJECT_BANK_DIR = Path(__file__).parent.parent / "object_bank"

# Terrain classes where each object category is allowed
PLACEMENT_RULES: Dict[str, List[int]] = {
    "person": [100, 101, 104, 106, 110, 111, 112, 113],
    "tractor": [100, 101, 104, 106, 110, 111, 112, 113],
    "pole": [100, 101, 105, 106],
    "rock": [100, 101, 102, 103, 104],
    "bush": [100, 101, 104, 105],
    "bag": [100, 101, 110, 111, 113],
}


class PlacedObject:
    def __init__(self, class_name: str, instance_id: str, transform: dict, asset_meta: dict):
        self.class_name = class_name
        self.instance_id = instance_id
        self.transform = transform
        self.asset_meta = asset_meta
        self.relit = False
        self.shadow_cast = False


class SceneCompositor:
    def __init__(self, seed: int = 42):
        self._seed = seed
        self._rng = random.Random(seed)
        self._scene_name: Optional[str] = None
        self._scene_data: Optional[dict] = None
        self._placed_objects: List[PlacedObject] = []

    def load_scene(self, scene_name: str):
        scene_path = SCENE_LIBRARY_DIR / scene_name
        if not scene_path.exists():
            raise FileNotFoundError(
                f"Scene '{scene_name}' not found in {SCENE_LIBRARY_DIR}. "
                f"Available: {[d.name for d in SCENE_LIBRARY_DIR.iterdir() if d.is_dir()]}"
            )
        self._scene_name = scene_name
        # TODO: load actual GS scene data (splat file + metadata)
        self._scene_data = {"name": scene_name, "path": str(scene_path)}

    def reset(self, seed: int):
        self._rng = random.Random(seed)
        self._placed_objects = []

    def place_object(self, class_name: str, seed: Optional[int] = None):
        """
        Place an object using proxy geometry for collision/terrain checks.
        Does NOT use raw splats for placement validation.
        """
        rng = random.Random(seed) if seed else self._rng
        asset = self._load_object_asset(class_name)
        if asset is None:
            return

        transform = self._sample_placement(class_name, asset, rng)
        if transform is None:
            return

        obj = PlacedObject(
            class_name=class_name,
            instance_id=f"{class_name}_{len(self._placed_objects):04d}",
            transform=transform,
            asset_meta=asset,
        )
        self._placed_objects.append(obj)

    def validate_placement(self):
        """Check all placement constraints using proxy geometry."""
        valid = []
        for obj in self._placed_objects:
            if self._check_no_floating(obj) and \
               self._check_no_sinking(obj) and \
               self._check_no_intersection(obj, valid):
                valid.append(obj)
        self._placed_objects = valid

    def apply_relighting(self):
        """
        Apply post-insertion lighting adaptation (D3DR-style).
        Adjusts object appearance to match scene lighting.
        NOT manual light parameter tuning.
        """
        for obj in self._placed_objects:
            # TODO: implement D3DR-inspired relighting
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
        Render all passes needed for label generation.
        Labels are generated from these passes, NOT from final RGB.
        Shadow pass uses proxy mesh geometry.
        """
        passes = {}
        if rgb:
            passes["rgb"] = self._render_rgb_pass()
        if object_id:
            passes["object_id"] = self._render_object_id_pass()
        if semantic:
            passes["semantic"] = self._render_semantic_pass()
        if depth:
            passes["depth"] = self._render_depth_pass()
        if shadow:
            passes["shadow"] = self._render_shadow_pass()
        return passes

    def get_object_states(self) -> List[dict]:
        return [
            {
                "class_name": obj.class_name,
                "instance_id": obj.instance_id,
                "transform": obj.transform,
                "proxy_bbox": obj.asset_meta.get("oriented_bbox"),
                "class_id": obj.asset_meta.get("class_id"),
            }
            for obj in self._placed_objects
        ]

    # ── Private ────────────────────────────────────────────────────────────

    def _load_object_asset(self, class_name: str) -> Optional[dict]:
        asset_dir = OBJECT_BANK_DIR / class_name
        if not asset_dir.exists():
            print(f"[Compositor] Warning: no asset for class '{class_name}'")
            return None
        # TODO: load actual asset metadata from yaml
        return {"class_id": list(PLACEMENT_RULES.keys()).index(class_name) if class_name in PLACEMENT_RULES else 99}

    def _sample_placement(self, class_name: str, asset: dict, rng: random.Random) -> Optional[dict]:
        # TODO: terrain-aware placement using heightmap + semantic map
        return {
            "x": rng.uniform(-50, 50),
            "y": rng.uniform(-50, 50),
            "z": 0.0,
            "yaw": rng.uniform(0, 360),
        }

    def _check_no_floating(self, obj: PlacedObject) -> bool:
        # TODO: check via terrain heightmap
        return True

    def _check_no_sinking(self, obj: PlacedObject) -> bool:
        # TODO: check via terrain heightmap
        return True

    def _check_no_intersection(self, obj: PlacedObject, existing: List[PlacedObject]) -> bool:
        # TODO: check via proxy mesh / oriented bbox
        return True

    def _render_rgb_pass(self):
        # TODO: GS renderer RGB pass
        return None

    def _render_object_id_pass(self):
        # TODO: per-object ID mask from proxy geometry
        return None

    def _render_semantic_pass(self):
        # TODO: semantic label mask
        return None

    def _render_depth_pass(self):
        # TODO: depth from GS + proxy geometry
        return None

    def _render_shadow_pass(self):
        # Shadow pass uses proxy mesh geometry, NOT natural RGB shadows
        # TODO: shadow casting from proxy mesh
        return None
