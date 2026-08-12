#!/usr/bin/env python3
"""Patch multiview_utils.py to clear diffusers' dynamic-module cache before
loading the paint pipeline.

The worker's HF cache lives on a persistent network volume. A stale
`diffusers_modules` directory (left by an earlier diffusers version or an
interrupted download) makes the dynamic import of the paint model's
``unet/modules.py`` fail with:

    ModuleNotFoundError: No module named 'diffusers_modules.local.modules'

Local reproduction with a clean cache loads fine, so we simply purge the
dynamic-module cache right before DiffusionPipeline.from_pretrained. The
module files are re-copied on every load, so this is safe.

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
        import shutil as _shutil
        _cache_root = _os.environ.get(
            "HF_MODULES_CACHE",
            _os.path.join(
                _os.environ.get("HF_HOME", _os.path.expanduser("~/.cache/huggingface")),
                "modules",
            ),
        )
        _dyn_modules = _os.path.join(_cache_root, "diffusers_modules")
        if _os.path.isdir(_dyn_modules):
            _shutil.rmtree(_dyn_modules, ignore_errors=True)
        pipeline = DiffusionPipeline.from_pretrained(
            model_path,
            custom_pipeline=custom_pipeline,
            torch_dtype=torch.float16
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
