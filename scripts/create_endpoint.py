#!/usr/bin/env python3
"""Create a RunPod Serverless endpoint for the Hunyuan3D worker.

Env:
  RUNPOD_API_KEY   required
  IMAGE            docker image, e.g. docker.io/user/runpod-hunyuan3d:2.1
  ENDPOINT_NAME    default: hunyuan3d-21
  GPU_IDS          default: NVIDIA RTX A6000,NVIDIA A40  (48GB tier)
  NETWORK_VOLUME_ID optional
  VOLUME_MOUNT     default: /runpod-volume
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

API = "https://api.runpod.io/graphql"


def gql(api_key: str, query: str, variables: dict | None = None) -> dict:
    payload = {"query": query, "variables": variables or {}}
    req = urllib.request.Request(
        API,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = json.loads(resp.read().decode())
    if body.get("errors"):
        raise RuntimeError(json.dumps(body["errors"], indent=2))
    return body["data"]


def main() -> int:
    api_key = os.environ.get("RUNPOD_API_KEY")
    image = os.environ.get("IMAGE")
    if not api_key or not image:
        print("Set RUNPOD_API_KEY and IMAGE", file=sys.stderr)
        return 2

    name = os.environ.get("ENDPOINT_NAME", "hunyuan3d-21")
    gpu_ids = os.environ.get("GPU_IDS", "NVIDIA RTX A6000,NVIDIA A40")
    volume_id = os.environ.get("NETWORK_VOLUME_ID")
    mount = os.environ.get("VOLUME_MOUNT", "/runpod-volume")

    # Create template then endpoint (RunPod GraphQL may vary by account; fallback prints manual steps)
    query = """
    mutation SaveTemplate($input: SaveTemplateInput!) {
      saveTemplate(input: $input) {
        id
        name
        imageName
      }
    }
    """
    variables = {
        "input": {
            "name": f"{name}-template",
            "imageName": image,
            "isServerless": True,
            "dockerStartCmd": [],
            "containerDiskInGb": 40,
            "volumeMountPath": mount,
            "env": [
                {"key": "HF_HOME", "value": f"{mount}/huggingface"},
                {"key": "LOW_VRAM", "value": "1"},
                {"key": "DEVICE", "value": "cuda"},
            ],
        }
    }
    if volume_id:
        variables["input"]["volumeId"] = volume_id

    try:
        data = gql(api_key, query, variables)
        template = data["saveTemplate"]
        print("Template:", json.dumps(template, indent=2))
    except Exception as e:
        print("Auto template creation failed (API shape may differ):", e)
        print(
            "\nManual steps:\n"
            "1) RunPod Console → Serverless → New Endpoint\n"
            f"2) Container image: {image}\n"
            "3) GPU: 48GB (A6000/A40) or 24GB 4090\n"
            "4) Flex workers, active=0, max=1\n"
            f"5) Network Volume mount: {mount}\n"
            "6) Container disk >= 40GB\n"
            "7) Execution timeout >= 900s\n"
        )
        return 1

    print("Create endpoint in console from this template, or extend this script with saveEndpoint mutation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
