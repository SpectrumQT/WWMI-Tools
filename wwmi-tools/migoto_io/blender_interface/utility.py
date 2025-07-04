import math
import mathutils

from pathlib import Path
from typing import Tuple

import bpy


def get_workdir() -> Path:
    return Path(bpy.path.abspath("//"))


def get_blend_file_path() -> Path:
    return Path(bpy.data.filepath)


def resolve_path(path) -> Path:
    abspath = bpy.path.abspath(path)
    if abspath is None:
        abspath = path
    return Path(abspath).resolve()


def get_scale_matrix(scale: Tuple[float], invert = False):
    if invert:
        scale = tuple(1.0 / s if s != 0 else 0.0 for s in scale)
    return mathutils.Matrix.Diagonal((scale[0], scale[1], scale[2], 1.0)).to_4x4()


def to_radians(rotation: Tuple[float]):
    return tuple(map(math.radians, rotation))


def get_rotation_matrix(rotation: Tuple[float], invert = False):
    rotation_matrix = mathutils.Euler(rotation, 'XYZ').to_matrix().to_4x4()
    if invert:
        rotation_matrix = rotation_matrix.inverted()
    return rotation_matrix