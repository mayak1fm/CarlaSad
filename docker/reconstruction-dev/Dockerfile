FROM nvidia/cuda:12.1.0-cudnn8-devel-ubuntu22.04

# Build context: project root
# CarlaSad world reconstruction pipeline: SfM → GS → mesh → CARLA import

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    git \
    cmake \
    libboost-all-dev \
    libeigen3-dev \
    libopencv-dev \
    libsuitesparse-dev \
    libgoogle-glog-dev \
    libgflags-dev \
    libglew-dev \
    qtbase5-dev \
    libqt5opengl5-dev \
    colmap \
    && rm -rf /var/lib/apt/lists/*

RUN ln -sf /usr/bin/python3.10 /usr/bin/python3 && \
    ln -sf /usr/bin/python3.10 /usr/bin/python

# PyTorch + nerfstudio (heavy, separate layer)
RUN pip install --no-cache-dir \
    torch torchvision --index-url https://download.pytorch.org/whl/cu121

RUN pip install --no-cache-dir \
    nerfstudio \
    open3d \
    trimesh \
    numpy \
    scipy \
    pillow \
    opencv-python-headless \
    pyyaml \
    imageio

WORKDIR /workspace/reconstruction
COPY tools/reconstruction/ .
