#!/usr/bin/env bash
# Create RunPod Serverless template + endpoint for Hunyuan3D worker.
# Requires: RUNPOD_API_KEY, IMAGE
# Optional: NETWORK_VOLUME_ID, CONTAINER_REGISTRY_AUTH_ID, ENDPOINT_NAME
set -euo pipefail

: "${RUNPOD_API_KEY:?Set RUNPOD_API_KEY}"
: "${IMAGE:?Set IMAGE}"

export NAME="${ENDPOINT_NAME:-hunyuan3d-21}"
export VOLUME_ID="${NETWORK_VOLUME_ID:-09efjbub1t}"
export AUTH_ID="${CONTAINER_REGISTRY_AUTH_ID:-}"
API="https://rest.runpod.io/v1"

curl_json() {
  local method=$1 url=$2
  shift 2
  curl -sS --retry 8 --retry-delay 3 --retry-all-errors \
    -X "$method" "$url" \
    -H "Authorization: Bearer $RUNPOD_API_KEY" \
    -H "Content-Type: application/json" \
    "$@"
}

python3 - <<'PY'
import json, os, time
body = {
  "name": f"{os.environ['NAME']}-tpl-{int(time.time())}",
  "imageName": os.environ["IMAGE"],
  "isServerless": True,
  "containerDiskInGb": 50,
  "volumeMountPath": "/runpod-volume",
  "env": {
    "HF_HOME": "/runpod-volume/huggingface",
    "TRANSFORMERS_CACHE": "/runpod-volume/huggingface/transformers",
    "HF_HUB_CACHE": "/runpod-volume/huggingface/hub",
    "LOW_VRAM": "1",
    "DEVICE": "cuda",
  },
  "dockerStartCmd": [],
}
auth = os.environ.get("AUTH_ID")
if auth:
    body["containerRegistryAuthId"] = auth
json.dump(body, open("/tmp/rp_template.json", "w"))
print("template:", body["name"])
PY

echo "Creating serverless template..."
TMPL=$(curl_json POST "$API/templates" --data-binary @/tmp/rp_template.json)
echo "$TMPL" | python3 -m json.tool
TEMPLATE_ID=$(echo "$TMPL" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
export TEMPLATE_ID

python3 - <<'PY'
import json, os
body = {
  "name": os.environ["NAME"],
  "templateId": os.environ["TEMPLATE_ID"],
  "gpuTypeIds": ["NVIDIA RTX A6000", "NVIDIA A40", "NVIDIA GeForce RTX 4090"],
  "gpuCount": 1,
  "workersMin": 0,
  "workersMax": 1,
  "idleTimeout": 20,
  "executionTimeoutMs": 1200000,
  "scalerType": "QUEUE_DELAY",
  "scalerValue": 4,
  "networkVolumeIds": [os.environ["VOLUME_ID"]],
  "flashboot": True,
}
json.dump(body, open("/tmp/rp_endpoint.json", "w"))
PY

echo "Creating endpoint..."
EP=$(curl_json POST "$API/endpoints" --data-binary @/tmp/rp_endpoint.json)
echo "$EP" | python3 -m json.tool
EP_ID=$(echo "$EP" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo ""
echo "ENDPOINT_ID=$EP_ID"
echo "IMAGE=$IMAGE"
echo "VOLUME=$VOLUME_ID"
