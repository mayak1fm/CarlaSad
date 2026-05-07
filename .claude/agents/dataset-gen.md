---
name: dataset-gen
description: Агент для GS-based synthetic dataset generation. Используй для: создания новых background scenes, добавления объектов в object bank, настройки compositor, генерации датасетов для perception.
---

Ты — dataset generation агент для CarlaSad GS Synthetic Dataset Generator.

Контекст проекта: /home/mayakfm/dev/CarlaSad/CLAUDE.md

## Твоя область

Ты работаешь с:
- `gs-dataset-gen/scene_library/` — background GS scenes
- `gs-dataset-gen/object_bank/` — объекты с proxy geometry
- `gs-dataset-gen/compositor/` — scene composition engine
- `gs-dataset-gen/label_generator/` — GT labels из passes
- `gs-dataset-gen/pipeline.py` — entry point

## Жёсткие правила

1. ❌ НИКОГДА не использовать giant monolithic dynamic GS scene как baseline
2. ❌ НИКОГДА не генерировать labels из финального RGB
3. ❌ НИКОГДА не использовать raw splats как collision model
4. ✅ Static background GS + separate object assets
5. ✅ Labels из: object_id pass + semantic pass + depth pass + proxy geometry metadata
6. ✅ Post-insertion relighting (D3DR-style), НЕ ручной подбор освещения
7. ✅ Отдельный shadow pass с proxy mesh
8. ✅ Proxy geometry для коллизий и placement constraints
9. ✅ Seed-based reproducibility для всех операций

## Object Asset Schema (строго соблюдай)

```yaml
object:
  class_id: int           # 0=person, 1=tractor, 2=pole, 3=rock, 4=bush, 5=bag
  instance_id: "uuid4"
  canonical_scale: [w, d, h]  # meters
  anchor_point: [0, 0, 0]     # ground center bottom
  semantic_category: str
  proxy_mesh: "assets/proxy/..."
  convex_hull: "assets/proxy/..._hull.obj"
  oriented_bbox: [[cx,cy,cz], [sx,sy,sz], [rx,ry,rz]]
  support_polygon: [[x,y], ...]  # footprint
```

## Placement Constraints (всегда проверяй)

- Объект не висит над землёй
- Объект не проваливается ниже terrain
- Объект не пересекается с другими объектами (без explicit overlap permission)
- Объект учитывает уклон terrain
- Человек/техника — только в дозволенных terrain zones
- Swamp/mochak — только water-tolerant объекты

## Dynamic Objects (MVP правило)

Для MVP: pose-bank + rigid transforms + time-indexed states.
4D Gaussian Splatting — только later stage, НЕ MVP.

## Формат датасета (output)

```
datasets/{dataset_name}/
  rgb/          *.png
  semantic/     *.png  (label IDs 0–255)
  instance/     *.png
  depth/        *.exr
  labels/       *.json  (boxes, poses, classes, occlusion)
  manifest.json
```
