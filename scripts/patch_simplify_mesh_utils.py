#!/usr/bin/env python3
"""Patch simplify_mesh_utils.py to decimate with pymeshlab instead of open3d.

The texture pipeline remeshes the mesh via
trimesh.mesh.simplify_quadric_decimation, which lazily imports open3d
(filtered out of the slim worker image). pymeshlab is already installed, so
use its quadric-edge-collapse filter instead.

Idempotent.
"""

from __future__ import annotations

import sys
from pathlib import Path


OLD = """    ms.save_current_mesh(outputpath.replace(".glb", ".obj"), save_textures=False)
    # 调用减面函数
    courent = trimesh.load(outputpath.replace(".glb", ".obj"), force="mesh")
    face_num = courent.faces.shape[0]

    if face_num > target_count:
        courent = courent.simplify_quadric_decimation(target_count)
    courent.export(outputpath)"""

NEW = """    ms.save_current_mesh(outputpath.replace(".glb", ".obj"), save_textures=False)
    # 调用减面函数（pymeshlab；trimesh.simplify_quadric_decimation 依赖 open3d，镜像未装）
    obj_path = outputpath.replace(".glb", ".obj")
    ms.load_new_mesh(obj_path)
    if ms.current_mesh().face_number() > target_count:
        ms.meshing_decimation_quadric_edge_collapse(
            targetfacenum=target_count,
            preserveboundary=True,
            preservetopology=True,
            optimalplacement=True,
        )
        ms.save_current_mesh(obj_path)
    courent = trimesh.load(obj_path, force="mesh")
    courent.export(outputpath)"""


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
        print("usage: patch_simplify_mesh_utils.py <path/to/simplify_mesh_utils.py>", file=sys.stderr)
        sys.exit(2)
    changed = patch(sys.argv[1])
    print("patched" if changed else "already patched or pattern not found")
    sys.exit(0)
