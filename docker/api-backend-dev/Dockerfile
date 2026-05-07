FROM python:3.11-slim

# CarlaSad Operator API backend

RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY api-backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY api-backend/ .

EXPOSE 8080 50051

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
