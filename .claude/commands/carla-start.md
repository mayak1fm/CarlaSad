---
description: Запустить CARLA runtime контейнер
---

Запусти CARLA runtime в Docker.

Аргументы: $ARGUMENTS

Возможные аргументы:
- `headless` — без дисплея (для серверов)
- `map <name>` — загрузить конкретную карту после старта
- `sync` — включить synchronous mode

Шаги:
1. `docker compose --profile runtime up -d carla-runtime`
2. Подожди CARLA порта 2000: `until docker compose exec carla-runtime nc -z localhost 2000; do sleep 2; done`
3. Проверь статус через MCP: `carla_status()`
4. Если передан аргумент `map`, загрузи: `carla_load_map(map_name)`
5. Если передан `sync`, включи: `carla_set_sync_mode(True)`
6. Сообщи итог
