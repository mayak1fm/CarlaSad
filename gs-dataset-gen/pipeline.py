#!/usr/bin/env python3
"""
CarlaSad GS Synthetic Dataset Generator — entry point.

Usage:
    python pipeline.py --scene field_sunny --objects person:3,tractor:1 --count 100 --seed 42
"""
import argparse
import sys
from pathlib import Path

from compositor.scene_compositor import SceneCompositor
from label_generator.generator import LabelGenerator
from compositor.dataset_writer import DatasetWriter


def parse_objects(objects_str: str) -> dict:
    if not objects_str:
        return {}
    result = {}
    for item in objects_str.split(","):
        parts = item.strip().split(":")
        cls = parts[0]
        count = int(parts[1]) if len(parts) > 1 else 1
        result[cls] = count
    return result


def main():
    parser = argparse.ArgumentParser(description="CarlaSad GS Synthetic Dataset Generator")
    parser.add_argument("--scene", default="field_sunny", help="Background scene name from scene_library/")
    parser.add_argument("--objects", default="", help="Objects to insert: class:count,... e.g. person:3,tractor:1")
    parser.add_argument("--count", type=int, default=100, help="Number of samples to generate")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--output", default="/datasets/generated", help="Output directory")
    parser.add_argument("--no-shadows", action="store_true", help="Skip shadow pass")
    parser.add_argument("--no-relight", action="store_true", help="Skip relighting pass")
    args = parser.parse_args()

    objects = parse_objects(args.objects)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"[CarlaSad Dataset Gen] Scene: {args.scene}")
    print(f"[CarlaSad Dataset Gen] Objects: {objects}")
    print(f"[CarlaSad Dataset Gen] Count: {args.count}, Seed: {args.seed}")
    print(f"[CarlaSad Dataset Gen] Output: {output_dir}")

    compositor = SceneCompositor(seed=args.seed)
    label_gen = LabelGenerator()
    writer = DatasetWriter(output_dir)

    compositor.load_scene(args.scene)

    for i in range(args.count):
        sample_seed = args.seed + i
        compositor.reset(seed=sample_seed)

        for cls, count in objects.items():
            for _ in range(count):
                compositor.place_object(cls, seed=sample_seed)

        compositor.validate_placement()

        if not args.no_relight:
            compositor.apply_relighting()

        passes = compositor.render_passes(
            rgb=True,
            object_id=True,
            semantic=True,
            depth=True,
            shadow=not args.no_shadows,
        )

        labels = label_gen.generate(passes, compositor.get_object_states())
        writer.write_sample(i, passes, labels)

        if (i + 1) % 10 == 0:
            print(f"[CarlaSad Dataset Gen] {i + 1}/{args.count} samples generated")

    writer.write_manifest({
        "scene": args.scene,
        "objects": objects,
        "count": args.count,
        "seed": args.seed,
    })

    print(f"[CarlaSad Dataset Gen] Done. Dataset at: {output_dir}")


if __name__ == "__main__":
    main()
