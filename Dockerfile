# RunPod Serverless worker: Hunyuan3D 2.1 (image/text → GLB)
# Slimmed for GitHub Actions disk limits (no conda CUDA metapackage).
FROM nvidia/cuda:12.4.1-devel-ubuntu22.04

LABEL name="runpod-hunyuan3d21" maintainer="runpod-hunyuan3d"

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYOPENGL_PLATFORM=egl \
    CUDA_HOME=/usr/local/cuda \
    TORCH_CUDA_ARCH_LIST="7.5;8.0;8.6;8.9;9.0" \
    HUNYUAN_ROOT=/workspace/Hunyuan3D-2.1 \
    HF_HOME=/runpod-volume/huggingface \
    TRANSFORMERS_CACHE=/runpod-volume/huggingface/transformers \
    HF_HUB_CACHE=/runpod-volume/huggingface/hub \
    OUTPUT_DIR=/tmp/hunyuan3d_jobs \
    LOW_VRAM=1 \
    DEVICE=cuda

ENV PATH=${CUDA_HOME}/bin:${PATH}
ENV LD_LIBRARY_PATH=${CUDA_HOME}/lib64:${LD_LIBRARY_PATH}

WORKDIR /workspace

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential git wget curl cmake ninja-build \
    libegl1-mesa-dev libglib2.0-0 pkg-config \
    libglvnd0 libgl1 libglx0 libegl1 libgles2 \
    libglvnd-dev libgl1-mesa-dev libgles2-mesa-dev \
    libxrender1 libeigen3-dev python3-dev python3-setuptools libcgal-dev \
    libxi6 libxkbcommon-x11-0 libsm6 libxext6 libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# Miniconda Python only (use system CUDA toolkit from base image — much smaller)
RUN wget -q https://repo.anaconda.com/miniconda/Miniconda3-py310_24.9.2-0-Linux-x86_64.sh -O /tmp/miniconda.sh && \
    bash /tmp/miniconda.sh -b -p /workspace/miniconda3 && \
    rm -f /tmp/miniconda.sh && \
    /workspace/miniconda3/bin/conda tos accept --channel https://repo.anaconda.com/pkgs/main && \
    /workspace/miniconda3/bin/conda tos accept --channel https://repo.anaconda.com/pkgs/r && \
    /workspace/miniconda3/bin/conda create -y -n hunyuan3d21 python=3.10 && \
    /workspace/miniconda3/bin/conda clean -afy && \
    rm -rf /workspace/miniconda3/pkgs /root/.conda/pkgs

ENV PATH="/workspace/miniconda3/envs/hunyuan3d21/bin:/workspace/miniconda3/bin:${PATH}"
ENV LD_LIBRARY_PATH="/workspace/miniconda3/envs/hunyuan3d21/lib:${LD_LIBRARY_PATH}"

RUN pip install --no-cache-dir torch==2.5.1 torchvision==0.20.1 torchaudio==2.5.1 \
    --index-url https://download.pytorch.org/whl/cu124 && \
    rm -rf /root/.cache /tmp/*

# Official Hunyuan3D-2.1 + filtered deps (skip UI / Blender / heavy unused pkgs)
RUN git clone --depth 1 https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1.git && \
    grep -vE '^(bpy|gradio|open3d|deepspeed|tb_nightly|tensorboard)([=<>]|$)' \
      Hunyuan3D-2.1/requirements.txt > /tmp/hy3d-requirements.txt && \
    pip install --no-cache-dir -r /tmp/hy3d-requirements.txt && \
    rm -rf /root/.cache /tmp/hy3d-requirements.txt /tmp/*

# CUDA extensions (need torch visible → no build isolation)
RUN cd /workspace/Hunyuan3D-2.1/hy3dpaint/custom_rasterizer && \
    export CUDA_NVCC_FLAGS="-allow-unsupported-compiler" && \
    pip install -e . --no-build-isolation && \
    cd /workspace/Hunyuan3D-2.1/hy3dpaint/DifferentiableRenderer && \
    bash compile_mesh_painter.sh && \
    mkdir -p /workspace/Hunyuan3D-2.1/hy3dpaint/ckpt && \
    wget -q https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth \
      -P /workspace/Hunyuan3D-2.1/hy3dpaint/ckpt && \
    cd /workspace/Hunyuan3D-2.1/hy3dpaint && \
    sed -i 's/self\.multiview_cfg_path = "cfgs\/hunyuan-paint-pbr\.yaml"/self.multiview_cfg_path = "hy3dpaint\/cfgs\/hunyuan-paint-pbr.yaml"/' textureGenPipeline.py && \
    sed -i 's/custom_pipeline = config\.custom_pipeline/custom_pipeline = os.path.join(os.path.dirname(__file__),"..","hunyuanpaintpbr")/' utils/multiview_utils.py && \
    find /workspace -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true && \
    rm -rf /root/.cache /tmp/* /workspace/miniconda3/pkgs

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt && rm -rf /root/.cache /tmp/*
COPY handler.py /app/handler.py
COPY worker /app/worker
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

ENV PYTHONPATH="/workspace/Hunyuan3D-2.1:/workspace/Hunyuan3D-2.1/hy3dshape:/workspace/Hunyuan3D-2.1/hy3dpaint:/app"

CMD ["/app/start.sh"]
