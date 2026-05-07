---
description: Переключить world mode (editor / reconstructed)
---

Переключи world mode CARLA симулятора.

Аргументы: $ARGUMENTS

Режимы:
- `editor [map_name]` — загрузить Editor World (статически собранная карта)
- `reconstructed [map_name]` — загрузить Reconstructed World (из SfM/GS данных)
- `list` — показать доступные карты в обоих режимах

Шаги для `list`:
1. Покажи карты из `maps/editor-worlds/`
2. Покажи карты из `maps/reconstructed-worlds/`
3. Покажи карты через MCP: `carla_list_maps()`

Шаги для смены режима:
1. Определи режим и имя карты из аргументов
2. Если карта не указана — используй дефолтную для режима
3. Загрузи карту через MCP: `carla_load_map(map_name)`
4. Обнови world_info топик через bridge config
5. Подтверди переключение: `carla_get_map_info()`
6. Сообщи новый mode и map name
