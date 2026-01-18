import os
import re

from dataclasses import dataclass, field
from pathlib import Path
from typing import List


@dataclass
class Texture:
    hash: str
    path: Path
    filename: str


def get_textures(object_source_folder: Path, exclude_hashes: List[str]):
    textures = {}
    for texture_filename in os.listdir(object_source_folder):
        if texture_filename.endswith(".dds") or texture_filename.endswith(".jpg"): 
            # Handle new format
            hash_pattern = re.compile(r'.*t=([a-f0-9]{8}).*')
            result = hash_pattern.findall(texture_filename.lower())
            
            if len(result) != 1:
                # Handle old format
                hash_pattern = re.compile(r'.*component_\d-ps-t\d-([a-f0-9]{8}).*')
                result = hash_pattern.findall(texture_filename.lower())
                if len(result) != 1:
                    continue

            texture_hash = result[0]

            if exclude_hashes and texture_hash in exclude_hashes:
                continue

            textures[texture_hash] = Texture(
                hash=texture_hash,
                path=object_source_folder / texture_filename,
                filename=texture_filename,
            )
    return list(textures.values())
