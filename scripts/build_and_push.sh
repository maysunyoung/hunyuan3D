#!/usr/bin/env bash
# Build linux/amd64 image and push to Docker Hub / GHCR.
# Requires: Docker buildx, enough disk (~40GB+), registry login.
set -euo pipefail

IMAGE="${IMAGE:-docker.io/${DOCKERHUB_USER:-YOUR_USER}/runpod-hunyuan3d:2.1}"
PLATFORM="${PLATFORM:-linux/amd64}"

echo "Building $IMAGE ($PLATFORM)"
docker buildx create --use --name hunyuan-builder 2>/dev/null || docker buildx use hunyuan-builder
docker buildx build \
  --platform "$PLATFORM" \
  -t "$IMAGE" \
  --push \
  .
echo "Pushed: $IMAGE"
echo "Next: create RunPod Serverless endpoint with this image + Network Volume on /runpod-volume"
