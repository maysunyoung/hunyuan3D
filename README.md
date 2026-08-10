# RunPod Hunyuan3D 2.1 Serverless Worker

自部署开源 **图生 3D / 文生 3D**（Hunyuan3D 2.1 + HunyuanDiT 文生图），面向 [RunPod Serverless](https://www.runpod.io/product/serverless)。

> 许可：Hunyuan 权重遵循腾讯社区许可（常见为非商业/有限制条款）。上线前请自行阅读仓库 `LICENSE`。

## 功能

| mode | 说明 |
|---|---|
| `image_to_3d` | 单图 → 白模 / 可选 PBR → GLB |
| `text_to_3d` | prompt → HunyuanDiT 出图 → 同上 |

可调参数：`with_texture`、`rembg`、`steps`、`guidance_scale`、`seed`、`octree_resolution`(256/384/512)、`max_num_view`、`texture_resolution`(512/768)。

## 1. 构建并推送镜像

本机磁盘通常不够（镜像很大）。**推荐用 GitHub Actions → GHCR**。

### A. GitHub Actions（推荐）

1. Push 本仓库到 GitHub  
2. **Actions → Build and Push RunPod Image → Run workflow**  
   - `registry`: `ghcr`（默认，用 `GITHUB_TOKEN`，不用 Docker Hub）  
   - `tag`: `2.1`  
3. 得到：`ghcr.io/<owner小写>/runpod-hunyuan3d:2.1`  
4. Package 设为 Public，或给 RunPod 配 `read:packages` PAT  

若 runner 磁盘不够失败，改用下方 B/C，或 workflow 选 `dockerhub`（需 Secrets：`DOCKERHUB_USERNAME`、`DOCKERHUB_TOKEN`）。

### B. 有足够磁盘的 Linux x86_64 构建机

```bash
export DOCKERHUB_USER=你的用户名
docker login
IMAGE=docker.io/$DOCKERHUB_USER/runpod-hunyuan3d:2.1 bash scripts/build_and_push.sh
```

### C. 在 RunPod 临时 Pod 上构建

1. 开一台高磁盘 Pod，挂载 Network Volume 到 `/runpod-volume`
2. clone 本仓库后 `docker build` + `docker push`

首次构建约 30–90 分钟。

## 2. Network Volume（强烈建议）

在 RunPod 创建 Network Volume（建议 **100GB+**，与 endpoint 同区域），挂载到：

```text
/runpod-volume
```

模型会缓存到 `/runpod-volume/huggingface`，避免每次冷启动重新下载。

可选：在任意 GPU Pod 上预先下载：

```bash
pip install huggingface_hub
huggingface-cli download tencent/Hunyuan3D-2.1 --local-dir /runpod-volume/huggingface/hub/models--tencent--Hunyuan3D-2.1
huggingface-cli download Tencent-Hunyuan/HunyuanDiT-v1.1-Diffusers-Distilled
```

## 3. 创建 Serverless Endpoint

Console → **Serverless → New Endpoint**：

| 配置 | 建议值 |
|---|---|
| Container image | `docker.io/<user>/runpod-hunyuan3d:2.1` |
| GPU | **48GB**（A6000/A40）；试跑可用 24GB 4090 |
| Workers | Flex，Active=0，Max=1（先） |
| Container disk | ≥ 40 GB |
| Volume | 挂到 `/runpod-volume` |
| Execution timeout | **900–1200 s** |
| Idle timeout | 10–30 s |

环境变量（可选）：

```text
HF_HOME=/runpod-volume/huggingface
LOW_VRAM=1
DEVICE=cuda
HUNYUAN_ROOT=/workspace/Hunyuan3D-2.1
```

## 4. 调用示例

```bash
export RUNPOD_API_KEY=...
export ENDPOINT_ID=...

# 图生 3D（异步）
curl -sS https://api.runpod.ai/v2/$ENDPOINT_ID/run \
  -H "Authorization: Bearer $RUNPOD_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "mode": "image_to_3d",
      "image_url": "https://example.com/cat.png",
      "with_texture": false,
      "steps": 30,
      "octree_resolution": 384,
      "rembg": true
    }
  }'

# 轮询
curl -sS https://api.runpod.ai/v2/$ENDPOINT_ID/status/<JOB_ID> \
  -H "Authorization: Bearer $RUNPOD_API_KEY"
```

文生 3D：

```json
{
  "input": {
    "mode": "text_to_3d",
    "prompt": "a cute brown seal, cartoon style, single object",
    "with_texture": true,
    "steps": 30,
    "octree_resolution": 384
  }
}
```

成功时返回 `glb_base64`（可解码保存为 `.glb`）。

```bash
python3 - <<'PY'
import base64, json, sys
data=json.load(sys.stdin)
open("out.glb","wb").write(base64.b64decode(data["glb_base64"]))
print("wrote out.glb")
PY
```

## 成本参考（Serverless）

- 48GB 档约 **$1.22/hr**（按秒计）
- 冷启动 + 生成一轮常见 **$0.05–0.13/次**
- Volume 100GB 约 **$7/月**

## 目录结构

```text
handler.py          # RunPod entry
worker/pipeline.py  # Hunyuan load + generate
Dockerfile          # CUDA 12.4 + Hunyuan3D 2.1 + handler
scripts/            # build / endpoint helpers
test_input.json
```

## 注意

1. 首次请求会很慢（拉权重进显存），务必挂 Volume。  
2. `with_texture=true` 建议 48GB；24GB 可能 OOM。  
3. 返回 `glb_base64` 体积大；生产建议改成上传 S3/R2 只返回 URL。  
4. 质量 ≈ 开源 2.1，不是 Fast3D 线上的 3.1 Pro。
