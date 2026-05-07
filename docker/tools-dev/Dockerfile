FROM python:3.10-slim

# Build context: project root
# CarlaSad tools: replay, tests, scenario runner

RUN apt-get update && apt-get install -y \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

RUN pip install --no-cache-dir \
    pytest \
    pytest-asyncio \
    pytest-cov \
    pyyaml \
    numpy \
    mcp

# CarlaSad Python package (carla dep optional — egg mounted at runtime)
COPY carla-fork/PythonAPI/carlasad /workspace/carlasad
RUN pip install --no-cache-dir -e /workspace/carlasad
