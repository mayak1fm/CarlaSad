FROM python:3.10-slim

# CarlaSad tools container: replay, tests, scenario runner

RUN apt-get update && apt-get install -y \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# CARLA Python API
ARG CARLA_VERSION=0.9.15
RUN pip install carla==${CARLA_VERSION} || true

RUN pip install \
    pytest \
    pytest-asyncio \
    pyyaml \
    numpy \
    mcp

COPY carla-fork/PythonAPI/carlasad /workspace/carlasad
RUN pip install -e /workspace/carlasad || true
