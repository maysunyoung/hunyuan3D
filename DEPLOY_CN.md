# 快速部署到 RunPod（中文）

本机磁盘不够构建大镜像时，按下面做。

## 你需要准备

1. GitHub 账号（推荐用 Actions 构建，推到 GHCR）  
2. [RunPod](https://www.runpod.io/) 账号 + API Key（Settings → API Keys）  
3. 本仓库代码（已在 `/Users/dawn/Dev/runpod-hunyuan3d`）

## 步骤 1：用 GitHub Actions 构建镜像（推荐）

不需要本机构建，也不需要先买 RunPod 构建机。

1. 把本仓库推到 GitHub（新建空仓库后）：

```bash
cd /Users/dawn/Dev/runpod-hunyuan3d
git remote add origin https://github.com/<你的用户名>/runpod-hunyuan3d.git
git add -A && git commit -m "Initial RunPod Hunyuan3D worker"
git push -u origin main
```

2. 仓库页 → **Actions** → **Build and Push RunPod Image** → **Run workflow**  
   - `tag`: `2.1`  
   - `registry`: **`ghcr`**（默认，无需 Docker Hub）

3. 跑完后镜像地址类似：

```text
ghcr.io/<你的用户名小写>/runpod-hunyuan3d:2.1
```

4. 首次建议把包设为 **Public**（Packages → 该镜像 → Package settings → Change visibility），RunPod 拉取最省事。  
   若保持 Private：在 RunPod Endpoint 填 Registry 凭据（GitHub PAT，`read:packages`）。

> 若 Actions 因磁盘不足失败：再改用下面「备用：RunPod 上构建」，或换 Docker Hub（需仓库 Secrets：`DOCKERHUB_USERNAME` / `DOCKERHUB_TOKEN`，workflow 选 `dockerhub`）。

### 备用：在 RunPod 上构建

1. Console → **Pods → Deploy**（磁盘建议 **≥80GB**）  
2. 拷代码上去后：

```bash
docker login
export DOCKERHUB_USER=你的dockerhub用户名
docker build -t docker.io/$DOCKERHUB_USER/runpod-hunyuan3d:2.1 .
docker push docker.io/$DOCKERHUB_USER/runpod-hunyuan3d:2.1
```

## 步骤 2：创建 Serverless Endpoint

1. **Serverless → New Endpoint**  
2. Container image: `ghcr.io/<你的用户名小写>/runpod-hunyuan3d:2.1`（或 Docker Hub 地址）  
3. GPU：**48GB（A6000/A40）**（贴图更稳；只要白模可用 4090）  
4. Active workers = **0**，Max workers = **1**（Flex）  
5. Container disk ≥ **40GB**  
6. Attach Network Volume → mount path **`/runpod-volume`**  
7. Execution timeout：**1200** 秒  
8. Env：

```text
HF_HOME=/runpod-volume/huggingface
LOW_VRAM=1
DEVICE=cuda
```

## 步骤 3：测试

```bash
export RUNPOD_API_KEY=xxx
export ENDPOINT_ID=xxx

curl -sS https://api.runpod.ai/v2/$ENDPOINT_ID/run \
  -H "Authorization: Bearer $RUNPOD_API_KEY" \
  -H "Content-Type: application/json" \
  -d @- <<'JSON'
{
  "input": {
    "mode": "image_to_3d",
    "image_url": "https://huggingface.co/datasets/huggingface/documentation-images/resolve/main/diffusers/cat.png",
    "with_texture": false,
    "steps": 20,
    "octree_resolution": 256,
    "rembg": true
  }
}
JSON
```

用返回的 `id` 去查：

```bash
curl -sS https://api.runpod.ai/v2/$ENDPOINT_ID/status/<JOB_ID> \
  -H "Authorization: Bearer $RUNPOD_API_KEY"
```

`COMPLETED` 后把 `output.glb_base64` 解码成文件即可。

## 文生 3D

```json
{
  "input": {
    "mode": "text_to_3d",
    "prompt": "a cute brown seal, cartoon, single object, white background",
    "with_texture": false,
    "steps": 30,
    "octree_resolution": 384
  }
}
```

首次会额外下载 HunyuanDiT，请保持 Volume 挂载。
