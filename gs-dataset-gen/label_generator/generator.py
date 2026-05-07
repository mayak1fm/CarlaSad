"""
Label generator for GS synthetic dataset.

Labels are generated from:
  - object_id pass
  - semantic pass
  - depth pass
  - visibility/occlusion analysis
  - proxy geometry metadata (oriented bbox, 3D pose)

NOT from final RGB.
"""
from typing import List, Optional
import json


class LabelGenerator:
    def generate(self, passes: dict, object_states: List[dict]) -> dict:
        """
        Generate all annotation types from render passes and proxy geometry.

        Returns:
            dict with: bboxes_2d, bboxes_3d, semantic_labels, instance_labels,
                       depth_labels, occlusion_metadata, pose_labels
        """
        labels = {
            "bboxes_2d": self._extract_2d_boxes(passes.get("object_id"), object_states),
            "bboxes_3d": self._extract_3d_boxes(object_states),
            "semantic_labels": self._extract_semantic(passes.get("semantic")),
            "instance_labels": self._extract_instances(passes.get("object_id"), object_states),
            "depth_labels": self._extract_depth_stats(passes.get("depth"), object_states),
            "occlusion_metadata": self._compute_occlusion(passes.get("object_id"), object_states),
            "pose_labels": self._extract_poses(object_states),
        }
        return labels

    def _extract_2d_boxes(self, object_id_pass, object_states: List[dict]) -> List[dict]:
        """Extract 2D bounding boxes from object_id pass, NOT from RGB."""
        boxes = []
        for obj in object_states:
            # TODO: project proxy bbox to image plane using camera matrix
            boxes.append({
                "instance_id": obj["instance_id"],
                "class_id": obj["class_id"],
                "class_name": obj["class_name"],
                "bbox_xyxy": [0, 0, 0, 0],  # TODO: from object_id_pass
                "confidence": 1.0,
            })
        return boxes

    def _extract_3d_boxes(self, object_states: List[dict]) -> List[dict]:
        """Extract 3D bounding boxes from proxy geometry."""
        boxes = []
        for obj in object_states:
            boxes.append({
                "instance_id": obj["instance_id"],
                "class_id": obj["class_id"],
                "transform": obj["transform"],
                "oriented_bbox": obj.get("proxy_bbox"),
            })
        return boxes

    def _extract_semantic(self, semantic_pass) -> Optional[str]:
        """Semantic label map path."""
        return None  # TODO: save semantic_pass as PNG

    def _extract_instances(self, object_id_pass, object_states: List[dict]) -> Optional[str]:
        """Instance label map — each object gets unique pixel color."""
        return None  # TODO: save object_id_pass as PNG

    def _extract_depth_stats(self, depth_pass, object_states: List[dict]) -> List[dict]:
        depth_stats = []
        for obj in object_states:
            depth_stats.append({
                "instance_id": obj["instance_id"],
                "mean_depth": None,  # TODO: from depth_pass masked by object_id_pass
                "min_depth": None,
                "max_depth": None,
            })
        return depth_stats

    def _compute_occlusion(self, object_id_pass, object_states: List[dict]) -> List[dict]:
        """Compute occlusion fraction per object from object_id pass."""
        occlusion = []
        for obj in object_states:
            occlusion.append({
                "instance_id": obj["instance_id"],
                "visible_fraction": 1.0,  # TODO: compare projected bbox area vs actual visible pixels
                "occluded_by": [],
            })
        return occlusion

    def _extract_poses(self, object_states: List[dict]) -> List[dict]:
        return [
            {
                "instance_id": obj["instance_id"],
                "class_id": obj["class_id"],
                "world_transform": obj["transform"],
            }
            for obj in object_states
        ]
