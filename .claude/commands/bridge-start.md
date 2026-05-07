---
description: Запустить ROS2 CARLA bridge для CarlaSad
---

Запусти CarlaSad ROS2 bridge.

Аргументы: $ARGUMENTS

Опции:
- `debug` — verbose logging
- `record` — включить rosbag2 запись
- `no-gt` — отключить ground truth топики

Шаги:
1. Убедись, что CARLA запущен: `carla_status()` — если нет, запусти `/carla-start`
2. Запусти bridge контейнер:
   ```
   docker compose --profile ros up -d ros2-bridge
   ```
3. Проверь что bridge подключился к CARLA (лог: "Connected to CARLA")
4. Проверь что топики появились:
   ```
   docker compose exec ros2-bridge ros2 topic list | grep -E '/tractor|/carlasad'
   ```
5. Если передан `record` — запусти rosbag2:
   ```
   docker compose exec ros2-bridge ros2 bag record -o /logs/session_$(date +%Y%m%d_%H%M%S) \
     /tractor/camera_front/image_raw /tractor/lidar/front/points /carlasad/ground_truth/ego_pose
   ```
6. Выведи список активных топиков и статус записи
