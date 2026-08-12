#!/usr/bin/env python3
"""Patch multiview_utils.py to load the 2.5D UNet from the in-repo package.

The paint model's unet/modules.py is loaded by diffusers through its dynamic
module mechanism, which has been flaky in this image (the module can be stale,
partial, or reference imports that fail) and surfaces as:

    ModuleNotFoundError: No module named 'diffusers_modules.local.modules'

The in-repo copy at hy3dpaint/hunyuanpaintpbr/unet/modules.py is known-good, so
we preload UNet2p5DConditionModel from there and pass it explicitly to
DiffusionPipeline.from_pretrained, skipping the dynamic module load entirely.

Idempotent.
"""

from __future__ import annotations

import sys
from pathlib import Path


OLD = """        pipeline = DiffusionPipeline.from_pretrained(
            model_path,
            custom_pipeline=custom_pipeline, 
            torch_dtype=torch.float16
        )"""

NEW = """        import os as _os
        import sys as _sys
        _hy3dpaint = _os.path.normpath(_os.path.join(_os.path.dirname(__file__), ".."))
        if _hy3dpaint not in _sys.path:
            _sys.path.insert(0, _hy3dpaint)
        from hunyuanpaintpbr.unet.modules import UNet2p5DConditionModel
        unet = UNet2p5DConditionModel.from_pretrained(
            _os.path.join(model_path, "unet"), torch_dtype=torch.float16
        )
        pipeline = DiffusionPipeline.from_pretrained(
            model_path,
            custom_pipeline=custom_pipeline,
            torch_dtype=torch.float16,
            unet=unet,
        )"""


def patch(path: str | Path) -> bool:
    p = Path(path)
    text = p.read_text()
    if NEW in text:
        return False
    if OLD not in text:
        return False
    p.write_text(text.replace(OLD, NEW, 1))
    return True


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: patch_multiview_utils.py <path/to/multiview_utils.py>", file=sys.stderr)
        sys.exit(2)
    changed = patch(sys.argv[1])
    print("patched" if changed else "already patched or pattern not found")
    sys.exit(0)
