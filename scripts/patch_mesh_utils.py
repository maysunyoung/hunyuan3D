#!/usr/bin/env python3
"""Make the bpy import in mesh_utils.py optional.

The texture pipeline (hy3dpaint) imports DifferentiableRenderer.mesh_utils at
module load time. mesh_utils.py does a hard `import bpy` (Blender), which is
not installed in the slim worker image. Our worker never calls
convert_obj_to_glb (pipeline.py uses save_glb=False and builds the GLB with
trimesh/pygltflib), so guarding the import is safe and keeps the image lean.

Idempotent: running twice leaves the file unchanged.
"""

from __future__ import annotations

import sys
from pathlib import Path


def patch(path: str | Path) -> bool:
    p = Path(path)
    text = p.read_text()
    old = "import bpy\n"
    new = (
        "try:\n"
        "    import bpy\n"
        "except ImportError:\n"
        "    bpy = None\n"
    )
    if old not in text:
        return False
    if new in text:
        return False
    # Only the first occurrence (module-level import in mesh_utils.py).
    p.write_text(text.replace(old, new, 1))
    return True


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: patch_mesh_utils.py <path/to/mesh_utils.py>", file=sys.stderr)
        sys.exit(2)
    changed = patch(sys.argv[1])
    print("patched" if changed else "already patched or pattern not found")
    sys.exit(0)
