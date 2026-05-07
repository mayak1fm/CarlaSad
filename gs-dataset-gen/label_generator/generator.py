"""
Label generator for GS synthetic dataset.

Labels are generated from:
  - object_id pass (numpy uint16 H×W — unique ID per object, 0=background)
  - semantic pass  (numpy uint8  H×W — CarlaSad label IDs 0–114)
  - depth pass     (numpy float32 H×W — depth in meters)
  - proxy geometry metadata (oriented bbox, 3D pose)

NOT from final RGB.
"""
from typing import List, Optional, Tuple
import numpy as np


class LabelGenerator:
    """
    Generate all annotation types from render passes and proxy geometry metadata.

    Inputs
    ------
    passes : dict produced by SceneCompositor.render_passes(), keys:
        "rgb"       np.ndarray H×W×3  uint8
        "object_id" np.ndarray H×W    uint16 (0=background, 1..N=objects)
        "semantic"  np.ndarray H×W    uint8
        "depth"     np.ndarray H×W    float32  (meters, 0=background)
        "shadow"    np.ndarray H×W    float32  (shadow mask 0–1)

    object_states : list of dicts from SceneCompositor.get_object_states()
        Each dict must have: instance_id(int), class_id(int), class_name(str),
                             transform(dict x/y/z/yaw), proxy_bbox(list)
    """

    def generate(self, passes: dict, object_states: List[dict]) -> dict:
        obj_id_pass  = passes.get("object_id")
        semantic_pass = passes.get("semantic")
        depth_pass   = passes.get("depth")

        labels = {
            "bboxes_2d":         self._extract_2d_boxes(obj_id_pass, object_states),
            "bboxes_3d":         self._extract_3d_boxes(object_states),
            "semantic_labels":   self._semantic_summary(semantic_pass),
            "instance_labels":   self._instance_summary(obj_id_pass, object_states),
            "depth_labels":      self._extract_depth_stats(depth_pass, obj_id_pass, object_states),
            "occlusion_metadata": self._compute_occlusion(obj_id_pass, object_states),
            "pose_labels":       self._extract_poses(object_states),
        }
        return labels

    # ── 2D bounding boxes ────────────────────────────────────────────────────

    def _extract_2d_boxes(self,
                          obj_id_pass: Optional[np.ndarray],
                          object_states: List[dict]) -> List[dict]:
        """Extract tight 2D bboxes from object_id pass. Never from RGB."""
        boxes = []
        if obj_id_pass is None:
            return boxes

        for obj in object_states:
            iid = int(obj["instance_id"])
            mask = (obj_id_pass == iid)
            if not mask.any():
                continue
            rows = np.where(mask.any(axis=1))[0]
            cols = np.where(mask.any(axis=0))[0]
            y1, y2 = int(rows[0]), int(rows[-1])
            x1, x2 = int(cols[0]), int(cols[-1])
            area = int(mask.sum())
            boxes.append({
                "instance_id": iid,
                "class_id":    int(obj["class_id"]),
                "class_name":  obj["class_name"],
                "bbox_xyxy":   [x1, y1, x2, y2],
                "bbox_xywh":   [x1, y1, x2 - x1, y2 - y1],
                "area_px":     area,
                "confidence":  1.0,
            })
        return boxes

    # ── 3D bounding boxes ────────────────────────────────────────────────────

    def _extract_3d_boxes(self, object_states: List[dict]) -> List[dict]:
        """3D bboxes come from proxy geometry — ground truth by construction."""
        boxes = []
        for obj in object_states:
            boxes.append({
                "instance_id":  int(obj["instance_id"]),
                "class_id":     int(obj["class_id"]),
                "class_name":   obj["class_name"],
                "transform":    obj["transform"],
                "oriented_bbox": obj.get("proxy_bbox"),
                "support_polygon": obj.get("support_polygon"),
            })
        return boxes

    # ── Semantic / instance maps ─────────────────────────────────────────────

    def _semantic_summary(self, semantic_pass: Optional[np.ndarray]) -> dict:
        if semantic_pass is None:
            return {}
        unique, counts = np.unique(semantic_pass, return_counts=True)
        total = semantic_pass.size
        return {
            "class_distribution": {
                int(u): {"count": int(c), "fraction": round(float(c) / total, 4)}
                for u, c in zip(unique, counts)
            }
        }

    def _instance_summary(self,
                          obj_id_pass: Optional[np.ndarray],
                          object_states: List[dict]) -> dict:
        if obj_id_pass is None:
            return {}
        unique_ids = [int(i) for i in np.unique(obj_id_pass) if i > 0]
        return {
            "num_instances": len(unique_ids),
            "instance_ids":  unique_ids,
        }

    # ── Depth stats per object ───────────────────────────────────────────────

    def _extract_depth_stats(self,
                             depth_pass: Optional[np.ndarray],
                             obj_id_pass: Optional[np.ndarray],
                             object_states: List[dict]) -> List[dict]:
        stats = []
        if depth_pass is None or obj_id_pass is None:
            return [{"instance_id": int(o["instance_id"]),
                     "mean_depth": None, "min_depth": None, "max_depth": None}
                    for o in object_states]

        for obj in object_states:
            iid  = int(obj["instance_id"])
            mask = (obj_id_pass == iid) & (depth_pass > 0)
            if not mask.any():
                stats.append({"instance_id": iid,
                               "mean_depth": None, "min_depth": None, "max_depth": None})
                continue
            vals = depth_pass[mask]
            stats.append({
                "instance_id": iid,
                "mean_depth":  round(float(vals.mean()), 3),
                "min_depth":   round(float(vals.min()), 3),
                "max_depth":   round(float(vals.max()), 3),
            })
        return stats

    # ── Occlusion ────────────────────────────────────────────────────────────

    def _compute_occlusion(self,
                           obj_id_pass: Optional[np.ndarray],
                           object_states: List[dict]) -> List[dict]:
        """
        Estimate visible fraction by comparing projected proxy bbox area
        against actually-visible pixel count in object_id pass.
        """
        occlusion = []
        if obj_id_pass is None:
            return [{"instance_id": int(o["instance_id"]),
                     "visible_fraction": 1.0, "occluded_by": []}
                    for o in object_states]

        h, w = obj_id_pass.shape

        for obj in object_states:
            iid  = int(obj["instance_id"])
            mask = (obj_id_pass == iid)
            visible_px = int(mask.sum())

            # Projected bbox area from proxy_bbox if available
            bbox_2d_area = self._project_proxy_bbox_area(obj, h, w)
            if bbox_2d_area > 0 and visible_px < bbox_2d_area:
                visible_fraction = round(float(visible_px) / float(bbox_2d_area), 4)
            else:
                visible_fraction = 1.0 if visible_px > 0 else 0.0

            # Detect what's occluding (objects whose id overlaps the projected region)
            occluded_by = []
            if visible_fraction < 0.99 and visible_px > 0:
                rows = np.where(mask.any(axis=1))[0]
                cols = np.where(mask.any(axis=0))[0]
                if len(rows) > 0 and len(cols) > 0:
                    region = obj_id_pass[rows[0]:rows[-1]+1, cols[0]:cols[-1]+1]
                    other_ids = [int(i) for i in np.unique(region) if i != iid and i != 0]
                    occluded_by = other_ids[:4]  # cap at 4

            occlusion.append({
                "instance_id":      iid,
                "visible_fraction": visible_fraction,
                "visible_px":       visible_px,
                "occluded_by":      occluded_by,
            })
        return occlusion

    def _project_proxy_bbox_area(self, obj: dict, img_h: int, img_w: int) -> int:
        """Rough projected proxy bbox area using oriented_bbox half-extents."""
        proxy = obj.get("proxy_bbox")
        if not proxy or len(proxy) < 2:
            return 0
        # half_extents in world-space meters; assume 1px ~= 0.02m at ~10m distance
        # This is a heuristic — real projection needs camera intrinsics
        try:
            half = proxy[1]   # [sx, sy, sz]
            area_m2 = 4.0 * float(half[0]) * float(half[2])  # width × height in world
            px_per_m2 = (img_h * img_w) / (50.0 * 50.0)      # rough: scene ~50×50 m visible
            return max(1, int(area_m2 * px_per_m2))
        except (IndexError, TypeError, ValueError):
            return 0

    # ── Poses ────────────────────────────────────────────────────────────────

    def _extract_poses(self, object_states: List[dict]) -> List[dict]:
        return [
            {
                "instance_id":    int(obj["instance_id"]),
                "class_id":       int(obj["class_id"]),
                "class_name":     obj["class_name"],
                "world_transform": obj["transform"],
            }
            for obj in object_states
        ]
