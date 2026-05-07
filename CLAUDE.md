# CarlaSad — CARLA Fork for Autonomous Agricultural Tractor Simulation

**Unreal fork**: https://github.com/mayak1fm/UnrealEngine  
**CARLA base**: 0.9.15 | **ROS2**: Humble | **Python**: 3.10  
**Dev model**: Docker-first, no host installs

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        CarlaSad Runtime                          │
│                                                                   │
│  ┌──────────────┐    ┌──────────────┐    ┌───────────────────┐  │
│  │  CARLA Fork  │◄──►│  ROS2 Bridge │◄──►│  Perception Stack │  │
│  │  (UE5 + C++) │    │  (carlasad_  │    │  (External ROS2)  │  │
│  │              │    │   bridge)    │    └───────────────────┘  │
│  └──────┬───────┘    └──────┬───────┘                           │
│         │                   │                                    │
│  ┌──────▼───────┐    ┌──────▼───────┐    ┌───────────────────┐  │
│  │  World Layer │    │  Logging     │    │  API Backend      │  │
│  │  - Editor    │    │  - rosbag2   │    │  (FastAPI/gRPC)   │  │
│  │  - Reconstructed   - JSON logs  │    │                   │  │
│  │  - Terrain   │    │  - Manifests │    └─────────┬─────────┘  │
│  │  - Process   │    └──────────────┘              │            │
│  └──────────────┘                                  │            │
│                                         ┌──────────▼──────────┐ │
│  ┌──────────────────────────────────┐   │  Dart Operator App  │ │
│  │  GS Synthetic Dataset Generator  │   │  (WebSocket/REST)   │ │
│  │  background_scene + object_bank  │   └─────────────────────┘ │
│  └──────────────────────────────────┘                           │
└─────────────────────────────────────────────────────────────────┘
```

---

## Module Map

| Module | Path | Impl Layer | Priority |
|--------|------|------------|----------|
| CARLA core (минимальные патчи) | `carla-fork/` | Unreal/C++ | P0 |
| Tractor vehicle asset | `carla-fork/Content/Vehicles/Tractor/` | Unreal | P0 |
| Thermal camera sensor | `carla-fork/Unreal/CarlaUE4/Plugins/Carla/Source/Carla/Sensor/` | C++ | P1 |
| Process/terrain semantics | `carla-fork/PythonAPI/carlasad/layers/` | Python | P0 |
| ROS2 bridge extension | `ros-bridge/carlasad_bridge/` | Python/ROS2 | P0 |
| Operator API backend | `api-backend/` | Python/FastAPI | P0 |
| GS dataset generator | `gs-dataset-gen/` | Python | P1 |
| World reconstruction pipeline | `tools/reconstruction/` | Python | P2 |
| MCP server (Claude tooling) | `tools/mcp-carla/` | Python/MCP | P0 |
| Docker stack | `docker/` + `docker-compose.yml` | Docker | P0 |

---

## Directory Structure

```
CarlaSad/
├── CLAUDE.md
├── docker-compose.yml           # Runtime profiles
├── docker-compose.dev.yml       # Dev overrides
├── .devcontainer/               # VS Code devcontainer
├── .claude/
│   ├── settings.json            # Hooks, MCP, permissions
│   ├── commands/                # Slash commands
│   └── agents/                  # Sub-agents
│
├── carla-fork/                  # Git submodule: github.com/mayak1fm/carla
│   ├── PythonAPI/carlasad/      # CarlaSad Python extensions
│   │   ├── layers/              # terrain, process, field_boundary
│   │   ├── world_modes/         # editor_world.py, reconstructed_world.py
│   │   ├── sensor_rig.py        # Sensor rig factory
│   │   ├── ground_truth.py      # GT export
│   │   └── logging/             # Logging modes
│   └── Unreal/CarlaUE4/...     # UE5 assets и патчи
│
├── ros-bridge/                  # Git submodule: github.com/mayak1fm/ros-bridge
│   └── carlasad_bridge/         # CarlaSad-специфичные extensions
│       ├── topic_contract.py    # ROS2 topic definitions
│       ├── process_publisher.py # Process layer topics
│       └── bridge_config.yaml   # Topic mapping config
│
├── api-backend/                 # Operator API (FastAPI + gRPC)
│   ├── main.py
│   ├── models/                  # Pydantic models
│   ├── routers/                 # REST endpoints
│   ├── ws/                      # WebSocket handlers
│   └── grpc/                    # gRPC proto + server
│
├── gs-dataset-gen/              # GS Synthetic Dataset Generator
│   ├── scene_library/           # Background GS scenes
│   ├── object_bank/             # Object assets + proxy geometry
│   ├── compositor/              # Scene composition engine
│   ├── label_generator/         # GT labels from passes
│   └── pipeline.py              # CLI entry point
│
├── docker/                      # Dockerfiles
│   ├── carla-runtime/
│   ├── carla-dev/
│   ├── ros2-bridge-dev/
│   ├── api-backend-dev/
│   ├── tools-dev/
│   ├── reconstruction-dev/
│   └── dataset-gen-dev/
│
├── maps/
│   ├── editor-worlds/           # Собранные в UE редакторе карты
│   └── reconstructed-worlds/    # Импортированные из SfM/GS
│
├── scenarios/
│   ├── scripts/                 # Python scenario scripts
│   └── configs/                 # YAML scenario configs
│
├── tools/
│   ├── mcp-carla/               # MCP server для Claude
│   └── reconstruction/          # SfM → CARLA map pipeline
│
├── datasets/                    # Output synthetic datasets
└── logs/                        # Simulation logs
```

---

## World Modes

### A. Editor World Mode
Статический мир, собранный в Unreal Editor.

```python
# carla-fork/PythonAPI/carlasad/world_modes/editor_world.py
from carlasad.layers import FieldBoundaryLayer, TerrainLayer, ProcessLayer

world = EditorWorld(
    map_name="Field_Main",
    terrain_config="configs/terrain/field_main.yaml",
    process_config="configs/process/default.yaml"
)
```

**Semantic labels (custom)**:
| ID | Label |
|----|-------|
| 100 | normal_field |
| 101 | wet_field |
| 102 | swamp |
| 103 | mochak |
| 104 | rough_terrain |
| 105 | field_boundary |
| 106 | drivable_path |
| 107 | non_drivable |
| 110 | worked_area |
| 111 | unworked_area |
| 112 | worked_edge |
| 113 | active_work_zone |
| 114 | restricted_zone |

### B. Reconstructed World Mode
Мир из реальных данных: фото/видео → SfM → GS → mesh → CARLA import.

```
реальные данные → COLMAP/OpenSfM → 3DGS → mesh extraction →
collision mesh → height map → CARLA custom map import
```

**Pipeline**: `tools/reconstruction/pipeline.py`  
**Output**: `.xodr` + `.fbx` + `terrain_heightmap.png` → CARLA

Оба режима экспортируют одинаковый runtime interface через `WorldInterface`.

---

## ROS2 Topic Contract

Все топики в `ros-bridge/carlasad_bridge/topic_contract.py`.

### Sensors
| Topic | Type | Notes |
|-------|------|-------|
| `/tractor/camera_{front,rear,left,right,fl,fr}/image_raw` | `sensor_msgs/Image` | 6 RGB cams |
| `/tractor/camera_{*}/camera_info` | `sensor_msgs/CameraInfo` | |
| `/tractor/lidar/front/points` | `sensor_msgs/PointCloud2` | |
| `/tractor/lidar/top/points` | `sensor_msgs/PointCloud2` | |
| `/tractor/radar/front` | `radar_msgs/RadarScan` | |
| `/tractor/gnss` | `sensor_msgs/NavSatFix` | |
| `/tractor/imu` | `sensor_msgs/Imu` | |
| `/tractor/thermal/image_raw` | `sensor_msgs/Image` | Custom sensor |

### World & Ground Truth
| Topic | Type | Notes |
|-------|------|-------|
| `/carla/clock` | `rosgraph_msgs/Clock` | |
| `/carlasad/world_info` | `carlasad_msgs/WorldInfo` | mode, map, weather |
| `/carlasad/ground_truth/ego_pose` | `geometry_msgs/PoseStamped` | |
| `/carlasad/ground_truth/objects` | `carlasad_msgs/ObjectArray` | |
| `/carlasad/ground_truth/semantic` | `sensor_msgs/Image` | |
| `/carlasad/ground_truth/instance` | `sensor_msgs/Image` | |
| `/carlasad/ground_truth/depth` | `sensor_msgs/Image` | |

### Process Layer
| Topic | Type | Notes |
|-------|------|-------|
| `/carlasad/process/worked_map` | `nav_msgs/OccupancyGrid` | |
| `/carlasad/process/worked_edge` | `carlasad_msgs/WorkedEdge` | |
| `/carlasad/process/field_boundary` | `geometry_msgs/PolygonStamped` | |
| `/carlasad/process/terrain_classes` | `nav_msgs/OccupancyGrid` | |
| `/carlasad/process/risk_map` | `nav_msgs/OccupancyGrid` | traversability |

### Mission
| Topic | Type | Notes |
|-------|------|-------|
| `/carlasad/mission/state` | `carlasad_msgs/MissionState` | |
| `/carlasad/mission/route` | `nav_msgs/Path` | |
| `/carlasad/mission/events` | `carlasad_msgs/MissionEvent` | |

### TF
- `map` → `odom` → `base_link` → sensor frames
- `base_link` → `{camera_front, lidar_front, ...}`

---

## Logging Modes

| Mode | Что пишет | Когда |
|------|-----------|-------|
| `online_debug` | sensor topics + tf + ego pose | dev runs |
| `dataset_recording` | все sensors + full GT + manifests | dataset gen |
| `scenario_replay` | seeds + actor states | regression |
| `passive_tick` | внешний orchestrator тикает sim | det. testing |
| `mission_log` | команды + маршрут + события + сенсоры | mission runs |

**Запись**: `carlasad/logging/recorder.py`  
**Форматы**: rosbag2 + JSON manifests + YAML scenario configs

---

## Operator API

**Backend**: FastAPI + WebSocket + optional gRPC  
**Port**: 8080 (REST/WS) / 50051 (gRPC)

### REST Endpoints
```
POST   /api/v1/mission/start
POST   /api/v1/mission/stop
GET    /api/v1/mission/status
POST   /api/v1/world/load       { map, mode }
POST   /api/v1/world/weather    { preset }
POST   /api/v1/sim/play
POST   /api/v1/sim/pause
POST   /api/v1/recording/start  { mode }
POST   /api/v1/recording/stop
GET    /api/v1/sessions          # replay browser
POST   /api/v1/replay/start     { session_id }
GET    /api/v1/sensor_rigs      # available profiles
POST   /api/v1/scenario/run     { scenario_id, seed }
```

### WebSocket
```
WS /ws/state     # streaming mission + sim state
WS /ws/events    # event notifications
```

---

## GS Synthetic Dataset Generator

**Entry point**: `gs-dataset-gen/pipeline.py`

### Pipeline Flow
```
background_scene (GS) + object_bank →
  compositor.place_objects() →
    lighting_adapter.relight() →
      shadow_compositor.add_shadows() →
        render_passes() →
          label_generator.from_passes() →
            dataset_writer.write()
```

### Что НЕ делать
- ❌ Giant monolithic dynamic GS scene
- ❌ Labels из финального RGB
- ❌ Raw splats как collision model
- ❌ Ручной подбор освещения

### Что делать (baseline)
- ✅ Static background GS + separate object assets
- ✅ Labels из object_id pass + semantic pass + depth + proxy geometry
- ✅ Post-insertion relighting (D3DR-style)
- ✅ Отдельный shadow pass с proxy mesh
- ✅ Proxy geometry для коллизий и placement constraints
- ✅ Seed-based reproducibility

### Object Asset Schema
```yaml
object:
  class_id: 1          # person
  instance_id: "uuid"
  canonical_scale: [0.5, 0.5, 1.8]
  anchor_point: [0, 0, 0]  # ground center
  semantic_category: "person"
  proxy_mesh: "assets/proxy/person_capsule.obj"
  convex_hull: "assets/proxy/person_hull.obj"
  oriented_bbox: [[x,y,z], [sx,sy,sz], [rx,ry,rz]]
  support_polygon: [[x1,y1], [x2,y2], ...]
```

---

## Dev Commands

```bash
# Поднять весь стек
docker compose --profile runtime up -d

# Dev режим с hot reload
docker compose -f docker-compose.yml -f docker-compose.dev.yml --profile dev up

# Только API backend
docker compose --profile api up

# Dataset generation run
docker compose --profile dataset-gen run --rm dataset-gen python pipeline.py \
  --scene field_sunny --objects person:3,tractor:1 --count 100 --seed 42

# Replay session
docker compose --profile replay run --rm tools replay \
  --session logs/session_20240101_120000/

# ROS2 bridge
docker compose --profile ros up

# Собрать CARLA fork (долго, ~1-2 часа)
docker compose --profile carla-build run --rm carla-dev \
  make CarlaUE4Editor ARGS=-game

# Python smoke test
docker compose --profile tools run --rm tools python -m pytest carla-fork/PythonAPI/carlasad/tests/
```

---

## Implementation Priorities

### P0 — MVP (weeks 1–4)
- [ ] Docker compose stack (runtime + bridge + api)
- [ ] Tractor vehicle asset (basic mesh + collision)
- [ ] Sensor rig (6 cams + 2 LiDAR + GNSS + IMU)
- [ ] ROS2 topic contract (sensors + tf + clock)
- [ ] Terrain semantic labels (100–114)
- [ ] Process layer basic (worked/unworked grid)
- [ ] Field boundary layer
- [ ] Operator API (REST + WebSocket)
- [ ] Online debug logging + rosbag2
- [ ] MCP server for Claude tooling

### P1 — Core (weeks 5–8)
- [ ] Thermal camera (custom CARLA sensor)
- [ ] Radar integration в bridge
- [ ] Dataset recording mode + manifests
- [ ] Scenario replay mode (seeds)
- [ ] Swamp/mochak terrain classes + physics
- [ ] GS dataset generator MVP (static scenes)
- [ ] Worked edge publisher
- [ ] Reconstructed world import pipeline (basic)
- [ ] Dart app operator UI (basic)

### P2 — Advanced (weeks 9+)
- [ ] Dynamic objects (pedestrians + farm machinery)
- [ ] 4DGS / dynamic GS for moving objects (research stage)
- [ ] Full reconstruction pipeline (COLMAP → GS → CARLA)
- [ ] DGSM-style shadow pipeline
- [ ] Risk map generation
- [ ] CI/CD smoke tests
- [ ] gRPC API layer
- [ ] Passive tick mode

---

## Interface Contract with Real Tractor

Эти интерфейсы должны совпадать с реальной машиной:

1. **TF tree** — фреймы `base_link`, все сенсорные фреймы
2. **Topic namespaces** — `/tractor/camera_*/`, `/tractor/lidar/`, `/tractor/gnss` etc.
3. **Message types** — стандартные ROS2 types везде где возможно
4. **Sensor parameters** — FOV, resolution, rate из реального rig
5. **GNSS datum** — тот же reference frame

---

## Risks & Technical Debt

| Риск | Влияние | Митигация |
|------|---------|-----------|
| CARLA build time ~2h | Slow CI | Кэшировать build artifacts |
| UE5 лицензия на сервере | CI blocker | Headless runtime-only в CI |
| Thermal sensor C++ сложность | P1 delay | Начать с RGB + постобработкой |
| GS lighting реализм | Dataset quality | D3DR-inspired pipeline |
| Dynamic actors в GS | Complexity | Pose-bank + rigid transforms для MVP |
| Real-world reconstruction качество | Map quality | SfM + manual cleanup |

---

## Submodule Setup

```bash
# После clone репозитория:
git submodule add https://github.com/mayak1fm/UnrealEngine carla-fork/Unreal
git submodule add https://github.com/carla-simulator/ros-bridge ros-bridge
git submodule update --init --recursive
```
