from __future__ import annotations

import os
import sys
import time
from typing import Any, Optional

import torch
from PIL import Image

APP_ROOT = os.environ.get("HUNYUAN_ROOT", "/workspace/Hunyuan3D-2.1")
MODEL_PATH = os.environ.get("HUNYUAN_MODEL_PATH", "tencent/Hunyuan3D-2.1")
SUBFOLDER = os.environ.get("HUNYUAN_SUBFOLDER", "hunyuan3d-dit-v2-1")
TEX_MODEL_PATH = os.environ.get("HUNYUAN_TEX_MODEL_PATH", MODEL_PATH)
HF_HOME = os.environ.get("HF_HOME", "/runpod-volume/huggingface")
LOW_VRAM = os.environ.get("LOW_VRAM", "1") == "1"
DEVICE = os.environ.get("DEVICE", "cuda" if torch.cuda.is_available() else "cpu")

os.environ.setdefault("HF_HOME", HF_HOME)
os.environ.setdefault("TRANSFORMERS_CACHE", os.path.join(HF_HOME, "transformers"))
os.environ.setdefault("HF_HUB_CACHE", os.path.join(HF_HOME, "hub"))

for p in (APP_ROOT, os.path.join(APP_ROOT, "hy3dshape"), os.path.join(APP_ROOT, "hy3dpaint")):
    if p not in sys.path:
        sys.path.insert(0, p)


_generator: Optional["Generator"] = None


class Generator:
    def __init__(self, with_texture: bool = False, enable_t23d: bool = False):
        self.device = DEVICE
        self.shape = None
        self.tex = None
        self.t2i = None
        self.rmbg = None
        self._tex_conf = None
        self._loaded_texture = False
        self._loaded_t23d = False
        self._init_shape()
        if with_texture:
            self._init_texture()
        if enable_t23d:
            self._init_t23d()

    def _init_shape(self) -> None:
        try:
            from torchvision_fix import apply_fix

            apply_fix()
        except Exception as e:
            print(f"[warn] torchvision_fix: {e}")

        from hy3dshape.pipelines import Hunyuan3DDiTFlowMatchingPipeline
        from hy3dshape.rembg import BackgroundRemover

        print(f"[init] loading shape model {MODEL_PATH}/{SUBFOLDER} on {self.device}")
        self.shape = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(
            MODEL_PATH,
            subfolder=SUBFOLDER,
            use_safetensors=False,
            device=self.device,
        )
        self.rmbg = BackgroundRemover()
        if LOW_VRAM:
            torch.cuda.empty_cache()

    def _init_texture(self) -> None:
        if self._loaded_texture:
            return
        from hy3dpaint.textureGenPipeline import Hunyuan3DPaintConfig, Hunyuan3DPaintPipeline

        conf = Hunyuan3DPaintConfig(max_num_view=6, resolution=512)
        conf.realesrgan_ckpt_path = os.path.join(APP_ROOT, "hy3dpaint/ckpt/RealESRGAN_x4plus.pth")
        conf.multiview_cfg_path = os.path.join(APP_ROOT, "hy3dpaint/cfgs/hunyuan-paint-pbr.yaml")
        conf.custom_pipeline = os.path.join(APP_ROOT, "hy3dpaint/hunyuanpaintpbr")
        print("[init] loading texture paint pipeline")
        self.tex = Hunyuan3DPaintPipeline(conf)
        self._tex_conf = conf
        self._loaded_texture = True
        if LOW_VRAM:
            torch.cuda.empty_cache()

    def _init_t23d(self) -> None:
        if self._loaded_t23d:
            return
        print("[init] loading HunyuanDiT text2image")
        model_id = os.environ.get(
            "T2I_MODEL_ID",
            "Tencent-Hunyuan/HunyuanDiT-v1.1-Diffusers-Distilled",
        )
        try:
            from hy3dgen.text2image import HunyuanDiTPipeline as OfficialT2I

            self.t2i = OfficialT2I(model_id)
            self._t2i_kind = "hy3dgen"
        except Exception as e:
            print(f"[warn] hy3dgen.text2image unavailable ({e}), fallback to diffusers")
            from diffusers import HunyuanDiTPipeline

            dtype = torch.float16 if self.device == "cuda" else torch.float32
            self.t2i = HunyuanDiTPipeline.from_pretrained(model_id, torch_dtype=dtype)
            if self.device == "cuda":
                self.t2i = self.t2i.to("cuda")
            self._t2i_kind = "diffusers"
        self._loaded_t23d = True
        if LOW_VRAM:
            torch.cuda.empty_cache()

    def ensure(self, with_texture: bool = False, enable_t23d: bool = False) -> None:
        if with_texture:
            self._init_texture()
        if enable_t23d:
            self._init_t23d()

    def text_to_image(self, prompt: str) -> Image.Image:
        self.ensure(enable_t23d=True)
        if self.t2i is None:
            raise RuntimeError("text2image model not loaded")
        if getattr(self, "_t2i_kind", "") == "diffusers":
            out = self.t2i(prompt=prompt).images[0]
        else:
            out = self.t2i(prompt)
            if isinstance(out, list):
                out = out[0]
        if not isinstance(out, Image.Image):
            raise RuntimeError(f"unexpected t2i output type: {type(out)}")
        return out.convert("RGBA")

    def generate(
        self,
        image: Image.Image,
        work_dir: str,
        with_texture: bool = False,
        rembg: bool = True,
        steps: int = 30,
        guidance_scale: float = 7.5,
        seed: Optional[int] = None,
        octree_resolution: int = 384,
        max_num_view: int = 6,
        texture_resolution: int = 512,
    ) -> dict[str, Any]:
        self.ensure(with_texture=with_texture)
        stats: dict[str, Any] = {"time": {}}
        t0 = time.time()

        if rembg or image.mode == "RGB":
            t = time.time()
            image = self.rmbg(image.convert("RGB"))
            stats["time"]["rembg"] = round(time.time() - t, 3)

        if seed is None:
            seed = int(torch.randint(0, 10_000_000, (1,)).item())
        generator = torch.Generator(device=self.device if self.device != "mps" else "cpu")
        generator = generator.manual_seed(int(seed))

        t = time.time()
        mesh = self.shape(
            image=image,
            num_inference_steps=steps,
            guidance_scale=guidance_scale,
            generator=generator,
            octree_resolution=octree_resolution,
            output_type="trimesh",
        )[0]
        stats["time"]["shape"] = round(time.time() - t, 3)

        white_path = os.path.join(work_dir, "white_mesh.glb")
        mesh.export(white_path)

        glb_path = white_path
        if with_texture:
            if self.tex is None:
                raise RuntimeError("texture pipeline not loaded")
            # update paint config if requested
            if self._tex_conf is not None:
                self._tex_conf.max_num_view = max_num_view
                self._tex_conf.resolution = texture_resolution

            obj_path = os.path.join(work_dir, "white_mesh.obj")
            mesh.export(obj_path)
            text_obj = os.path.join(work_dir, "textured_mesh.obj")
            t = time.time()
            self.tex(
                mesh_path=obj_path,
                image_path=image,
                output_mesh_path=text_obj,
                save_glb=False,
            )
            stats["time"]["texture"] = round(time.time() - t, 3)

            glb_path = os.path.join(work_dir, "textured_mesh.glb")
            try:
                from hy3dpaint.convert_utils import create_glb_with_pbr_materials

                textures = {
                    "albedo": text_obj.replace(".obj", ".jpg"),
                    "metallic": text_obj.replace(".obj", "_metallic.jpg"),
                    "roughness": text_obj.replace(".obj", "_roughness.jpg"),
                }
                create_glb_with_pbr_materials(text_obj, textures, glb_path)
            except Exception as e:
                print(f"[warn] PBR glb convert failed ({e}), fallback export")
                import trimesh

                m = trimesh.load(text_obj, force="mesh")
                m.export(glb_path)

        stats["time"]["total"] = round(time.time() - t0, 3)
        if LOW_VRAM:
            torch.cuda.empty_cache()
        return {"glb_path": glb_path, "seed": int(seed), "stats": stats}


def get_generator(with_texture: bool = False, enable_t23d: bool = False) -> Generator:
    global _generator
    if _generator is None:
        _generator = Generator(with_texture=with_texture, enable_t23d=enable_t23d)
    else:
        _generator.ensure(with_texture=with_texture, enable_t23d=enable_t23d)
    return _generator
