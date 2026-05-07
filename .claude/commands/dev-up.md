---
description: Поднять CarlaSad dev environment
---

Подними полный dev стек CarlaSad согласно профилю из аргумента.

Аргумент (profile): $ARGUMENTS

Доступные профили:
- `runtime` — CARLA + bridge + API (production-like)
- `dev` — то же с hot reload и volume mounts
- `api` — только API backend
- `ros` — только ROS2 bridge
- `dataset-gen` — только dataset generator
- `full` — всё

Выполни:
1. Проверь, что NVIDIA Docker runtime доступен: `docker info | grep -i nvidia`
2. Если профиль не указан, используй `dev`
3. Запусти: `docker compose -f docker-compose.yml -f docker-compose.dev.yml --profile {profile} up -d`
4. Подожди health checks: `docker compose ps`
5. Покажи статус всех контейнеров
6. Если CARLA запустился, проверь через MCP: `carla_status()`
7. Выведи итоговый статус: что запущено, что не запустилось и почему
