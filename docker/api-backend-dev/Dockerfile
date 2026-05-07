FROM python:3.11-slim

# Build context: project root

RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY api-backend/requirements.txt ./
# carla egg is mounted at runtime via carla-python-api volume, not installed here
RUN grep -v "^carla" requirements.txt | pip install --no-cache-dir -r /dev/stdin

COPY api-backend/ .

EXPOSE 8080 50051

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
