from __future__ import annotations

import base64
import io
import os
import uuid
from typing import Optional
from urllib.request import Request, urlopen

from PIL import Image

OUTPUT_ROOT = os.environ.get("OUTPUT_DIR", "/tmp/hunyuan3d_jobs")


def save_job_dir(job_id: str) -> str:
    path = os.path.join(OUTPUT_ROOT, job_id or str(uuid.uuid4()))
    os.makedirs(path, exist_ok=True)
    return path


def load_image(url: Optional[str] = None, b64: Optional[str] = None) -> Optional[Image.Image]:
    if b64:
        raw = b64.split(",", 1)[-1]
        data = base64.b64decode(raw)
        return Image.open(io.BytesIO(data)).convert("RGBA")
    if url:
        req = Request(url, headers={"User-Agent": "runpod-hunyuan3d/1.0"})
        with urlopen(req, timeout=120) as resp:
            data = resp.read()
        return Image.open(io.BytesIO(data)).convert("RGBA")
    return None


def upload_or_b64(path: str) -> str:
    """Return base64 of file. Optional S3 upload can be added later via env."""
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")
