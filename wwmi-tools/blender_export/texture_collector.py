import re

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Texture:
    path: Path
    filename: str
    components: list[int]
    hash: str
    dhash: str
    format: str
    prefix: str = ""
    suffix: str = ""


TEXTURE_NAME_PATTERN = re.compile(
    r"(?P<prefix>.*?)"
    r"(?<![a-z0-9_])c=(?P<component_ids>\d+(?:-\d+)*)"
    r"\s+f=(?P<format>[a-z0-9_]+)"
    r"\s+t=(?P<hash>[0-9a-f]{8})"
    r"\s+d=(?P<dhash>[0-9a-f]{16})"
    r"(?P<suffix>.*?)",
    re.IGNORECASE | re.DOTALL,
)


def parse_texture_filename(texture_path: Path) -> Texture | None:
    """Parse a texture filename, returning None if it doesn't match."""

    match = TEXTURE_NAME_PATTERN.fullmatch(texture_path.stem)
    if match is None:
        return None

    return Texture(
        path=texture_path,
        filename=texture_path.name,
        components=list(int(value) for value in match.group("component_ids").split("-")),
        hash=match.group("hash"),
        dhash=match.group("dhash"),
        format=match.group("format"),
        prefix=match.group("prefix").strip(),
        suffix=match.group("suffix").strip(),
    )


def get_textures(object_source_folder: Path, exclude_hashes: list[str]):
    textures = {}

    for texture_path in object_source_folder.iterdir():
        if not texture_path.suffix in (".dds", ".jpg"):
            continue

        texture = parse_texture_filename(texture_path)

        if texture is None:
            raise ValueError(f"Failed to parse texture filename `{texture_path.name}`")

        if exclude_hashes and texture.hash in exclude_hashes:
            continue
        
        textures[texture.hash] = texture

    return list(textures.values())
