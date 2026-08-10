#!/usr/bin/env bash
set -euo pipefail

mkdir -p "${HF_HOME:-/runpod-volume/huggingface}" "${OUTPUT_DIR:-/tmp/hunyuan3d_jobs}"

# Optional: pre-warm model list from volume (no-op if missing)
if [[ -d /runpod-volume/huggingface ]]; then
  echo "[start] HF cache: /runpod-volume/huggingface"
else
  echo "[start] WARNING: /runpod-volume not mounted; models will download to container disk"
fi

echo "[start] device=$(python - <<'PY'
import torch
print('cuda' if torch.cuda.is_available() else 'cpu', torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')
PY
)"

exec python -u /app/handler.py
