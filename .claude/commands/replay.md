---
description: Воспроизвести записанную сессию
---

Воспроизведи записанную сессию симуляции.

Аргументы (session path или ID): $ARGUMENTS

Шаги:
1. Найди сессию:
   - Если передан путь — используй его
   - Если передан ID — найди в `logs/` по паттерну
   - Если ничего — покажи последние 5 сессий в `logs/` и спроси
2. Проверь manifest: `{session}/manifest.json` — выведи: map, world_mode, scenario, duration, sensor_rig
3. Загрузи нужную карту через MCP: `carla_load_map(map_from_manifest)`
4. Запусти replay:
   ```
   docker compose --profile replay run --rm tools \
     python carla-fork/PythonAPI/carlasad/logging/replay.py \
     --session {session_path}
   ```
5. Если есть rosbag2 — предложи воспроизвести: `ros2 bag play {session_path}/rosbag2/`
6. Сообщи статус воспроизведения
