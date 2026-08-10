# RunPod Serverless worker: Hunyuan3D 2.1 (image/text → GLB)
# Based on official Tencent Hunyuan3D-2.1 docker/Dockerfile
FROM nvidia/cuda:12.4.1-devel-ubuntu22.04

LABEL name="runpod-hunyuan3d21" maintainer="runpod-hunyuan3d"

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYOPENGL_PLATFORM=egl
ENV CUDA_HOME=/usr/local/cuda
ENV PATH=${CUDA_HOME}/bin:${PATH}
ENV LD_LIBRARY_PATH=${CUDA_HOME}/lib64:${LD_LIBRARY_PATH}
ENV TORCH_CUDA_ARCH_LIST="7.0;7.5;8.0;8.6;8.9;9.0"
ENV HUNYUAN_ROOT=/workspace/Hunyuan3D-2.1
ENV HF_HOME=/runpod-volume/huggingface
ENV TRANSFORMERS_CACHE=/runpod-volume/huggingface/transformers
ENV HF_HUB_CACHE=/runpod-volume/huggingface/hub
ENV OUTPUT_DIR=/tmp/hunyuan3d_jobs
ENV LOW_VRAM=1
ENV DEVICE=cuda

RUN mkdir -p /workspace /app
WORKDIR /workspace

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential git wget vim unzip git-lfs curl cmake \
    libegl1-mesa-dev libglib2.0-0 pkg-config \
    libglvnd0 libgl1 libglx0 libegl1 libgles2 \
    libglvnd-dev libgl1-mesa-dev libgles2-mesa-dev mesa-utils-extra \
    libxrender1 libeigen3-dev python3-dev python3-setuptools libcgal-dev \
    libxi6 libgconf-2-4 libxkbcommon-x11-0 libsm6 libxext6 libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# Miniconda
RUN wget -q https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh && \
    chmod +x Miniconda3-latest-Linux-x86_64.sh && \
    ./Miniconda3-latest-Linux-x86_64.sh -b -p /workspace/miniconda3 && \
    rm Miniconda3-latest-Linux-x86_64.sh

ENV PATH="/workspace/miniconda3/bin:${PATH}"
RUN conda init bash && \
    conda tos accept --channel https://repo.anaconda.com/pkgs/main && \
    conda tos accept --channel https://repo.anaconda.com/pkgs/r && \
    conda config --set always_yes true

RUN conda create -n hunyuan3d21 python=3.10 && \
    conda install -n hunyuan3d21 Ninja && \
    conda install -n hunyuan3d21 cuda -c nvidia/label/cuda-12.4.1 -y && \
    conda install -n hunyuan3d21 -c conda-forge libstdcxx-ng -y

ENV PATH="/workspace/miniconda3/envs/hunyuan3d21/bin:${PATH}"
ENV LD_LIBRARY_PATH="/workspace/miniconda3/envs/hunyuan3d21/lib:${LD_LIBRARY_PATH}"

RUN pip install --no-cache-dir torch==2.5.1 torchvision==0.20.1 torchaudio==2.5.1 \
    --index-url https://download.pytorch.org/whl/cu124

# Official Hunyuan3D-2.1 source + deps
RUN git clone --depth 1 https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1.git
RUN pip install --no-cache-dir -r Hunyuan3D-2.1/requirements.txt

RUN cd /workspace/Hunyuan3D-2.1/hy3dpaint/custom_rasterizer && \
    export CUDA_NVCC_FLAGS="-allow-unsupported-compiler" && \
    pip install -e .

RUN cd /workspace/Hunyuan3D-2.1/hy3dpaint/DifferentiableRenderer && \
    bash compile_mesh_painter.sh

RUN mkdir -p /workspace/Hunyuan3D-2.1/hy3dpaint/ckpt && \
    wget -q https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth \
      -P /workspace/Hunyuan3D-2.1/hy3dpaint/ckpt

# Path fixes from official Dockerfile
RUN cd /workspace/Hunyuan3D-2.1/hy3dpaint && \
    sed -i 's/self\.multiview_cfg_path = "cfgs\/hunyuan-paint-pbr\.yaml"/self.multiview_cfg_path = "hy3dpaint\/cfgs\/hunyuan-paint-pbr.yaml"/' textureGenPipeline.py && \
    cd utils && \
    sed -i 's/custom_pipeline = config\.custom_pipeline/custom_pipeline = os.path.join(os.path.dirname(__file__),"..","hunyuanpaintpbr")/' multiview_utils.py

# RunPod worker code
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY handler.py /app/handler.py
COPY worker /app/worker
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

# Ensure torchvision fix module is importable
ENV PYTHONPATH="/workspace/Hunyuan3D-2.1:/workspace/Hunyuan3D-2.1/hy3dshape:/workspace/Hunyuan3D-2.1/hy3dpaint:/app:${PYTHONPATH}"

WORKDIR /app
CMD ["/app/start.sh"]
