"""RunPod Serverless handler for Hunyuan3D 2.1 (image/text to 3D)."""

from __future__ import annotations

import base64
import io
import os
import time
import traceback
import uuid
from typing import Any

import runpod

from worker.pipeline import Generator, get_generator
from worker.utils import load_image, save_job_dir, upload_or_b64


def _bool(v: Any, default: bool = False) -> bool:
    if v is None:
        return default
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in {"1", "true", "yes", "y", "on"}


def _int(v: Any, default: int) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _float(v: Any, default: float) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def handler(event: dict) -> dict:
    """
    Input schema:
      mode: image_to_3d | text_to_3d
      image_url / image_base64: for image_to_3d
      prompt: for text_to_3d
      with_texture: bool (default false)
      rembg: bool (default true)
      steps: int (default 30)
      guidance_scale: float (default 7.5)
      seed: int | null
      octree_resolution: 256|384|512 (default 384)
      max_num_view: 6-9 (texture)
      texture_resolution: 512|768
      return_base64: bool (default true)
    """
    started = time.time()
    job_input = event.get("input") or {}
    job_id = str(event.get("id") or uuid.uuid4())

    mode = (job_input.get("mode") or "image_to_3d").strip().lower()
    with_texture = _bool(job_input.get("with_texture"), False)
    rembg = _bool(job_input.get("rembg"), True)
    steps = _int(job_input.get("steps"), 30)
    guidance_scale = _float(job_input.get("guidance_scale"), 7.5)
    seed = job_input.get("seed")
    seed = None if seed is None else _int(seed, 1234)
    octree_resolution = _int(job_input.get("octree_resolution"), 384)
    max_num_view = _int(job_input.get("max_num_view"), 6)
    texture_resolution = _int(job_input.get("texture_resolution"), 512)
    return_base64 = _bool(job_input.get("return_base64"), True)

    if octree_resolution not in (256, 384, 512):
        octree_resolution = 384
    if texture_resolution not in (512, 768):
        texture_resolution = 512
    max_num_view = max(6, min(9, max_num_view))
    steps = max(5, min(100, steps))

    try:
        gen: Generator = get_generator(with_texture=with_texture, enable_t23d=(mode == "text_to_3d"))
        work_dir = save_job_dir(job_id)

        if mode == "text_to_3d":
            prompt = (job_input.get("prompt") or "").strip()
            if not prompt:
                return {"error": "prompt is required for text_to_3d"}
            image = gen.text_to_image(prompt)
            image_path = os.path.join(work_dir, "t2i.png")
            image.save(image_path)
        elif mode == "image_to_3d":
            image = load_image(
                url=job_input.get("image_url"),
                b64=job_input.get("image_base64"),
            )
            if image is None:
                return {"error": "image_url or image_base64 is required for image_to_3d"}
            image_path = os.path.join(work_dir, "input.png")
            image.save(image_path)
        else:
            return {"error": f"unsupported mode: {mode}"}

        result = gen.generate(
            image=image,
            work_dir=work_dir,
            with_texture=with_texture,
            rembg=rembg,
            steps=steps,
            guidance_scale=guidance_scale,
            seed=seed,
            octree_resolution=octree_resolution,
            max_num_view=max_num_view,
            texture_resolution=texture_resolution,
        )

        payload = {
            "job_id": job_id,
            "mode": mode,
            "seed": result["seed"],
            "with_texture": with_texture,
            "octree_resolution": octree_resolution,
            "steps": steps,
            "guidance_scale": guidance_scale,
            "stats": result.get("stats") or {},
            "elapsed_sec": round(time.time() - started, 3),
            "glb_path": result["glb_path"],
        }
        if return_base64:
            payload["glb_base64"] = upload_or_b64(result["glb_path"])
        if mode == "text_to_3d":
            # small preview of intermediate image
            buf = io.BytesIO()
            image.save(buf, format="JPEG", quality=85)
            payload["preview_image_base64"] = base64.b64encode(buf.getvalue()).decode("utf-8")
        return payload
    except Exception as e:
        traceback.print_exc()
        return {
            "error": str(e),
            "traceback": traceback.format_exc()[-4000:],
            "elapsed_sec": round(time.time() - started, 3),
        }


runpod.serverless.start({"handler": handler})
