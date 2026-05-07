FROM nvidia/cuda:12.1.0-cudnn8-devel-ubuntu22.04

# Build context: project root
# CarlaSad GS Synthetic Dataset Generator

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    python3.10-dev \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    git \
    wget \
    && rm -rf /var/lib/apt/lists/*

RUN ln -sf /usr/bin/python3.10 /usr/bin/python3 && \
    ln -sf /usr/bin/python3.10 /usr/bin/python

WORKDIR /workspace/gs-dataset-gen

# PyTorch first (large layer, cache-friendly ordering)
RUN pip install --no-cache-dir \
    torch torchvision --index-url https://download.pytorch.org/whl/cu121

COPY gs-dataset-gen/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY gs-dataset-gen/ .

EXPOSE 0
