---
description: Запустить GS synthetic dataset generation
---

Запусти пайплайн генерации synthetic dataset.

Аргументы: $ARGUMENTS

Формат аргументов: `--scene <scene_name> --objects <class:count,...> --count <N> --seed <S> --output <dir>`

Пример: `--scene field_sunny --objects person:3,tractor:1 --count 500 --seed 42`

Шаги:
1. Разбери аргументы из $ARGUMENTS
2. Если аргументов нет — используй дефолты: scene=field_sunny, count=100, seed=42
3. Проверь, что сцена существует в `gs-dataset-gen/scene_library/`
4. Запусти:
   ```
   docker compose --profile dataset-gen run --rm dataset-gen \
     python pipeline.py {parsed_args}
   ```
5. После завершения покажи:
   - Количество сгенерированных сэмплов
   - Путь к output
   - Размер датасета
   - Ошибки, если были
6. Проверь структуру output: должны быть rgb/, semantic/, instance/, depth/, labels/
