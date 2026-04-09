import json

from typing import List, Dict, Union, get_origin, get_args
from enum import Enum
from pathlib import Path
from dataclasses import dataclass, field, asdict, fields, is_dataclass

from ..migoto_io.data_model.dxgi_format import DXGIFormat
from ..migoto_io.data_model.byte_buffer import Semantic, AbstractSemantic, BufferSemantic, BufferLayout


@dataclass
class ExtractedObjectBufferSemantic:
    name: Semantic
    index: int
    format: DXGIFormat
    stride: int = 0

    def __post_init__(self):
        if isinstance(self.name, str):
            self.name = Semantic(self.name.upper())
        if isinstance(self.format, str):
            self.format = DXGIFormat(self.format.upper())
        if self.stride == 0:
            self.stride = self.format.byte_width

    def get_buffer_semantic(self):
        return BufferSemantic(AbstractSemantic(self.name, self.index), self.format, stride=self.stride)


@dataclass
class ExtractedObjectBuffer:
    semantics: List[ExtractedObjectBufferSemantic]

    def get_layout(self) -> BufferLayout:
        layout = BufferLayout([])
        for semantic in self.semantics:
            layout.add_element(semantic.get_buffer_semantic())
        return layout


@dataclass
class ExtractedObjectComponent:
    vertex_offset: int
    vertex_count: int
    index_offset: int
    index_count: int
    vg_offset: int
    vg_count: int
    vg_map: Dict[int, int]


@dataclass
class ExtractedObjectShapeKeysBatch:
    vertex_offset: int = 0
    vertex_count: int = 0
    shapekey_count: int = 0
    dispatch_y: int = 0
    checksum: int = 0


@dataclass
class ExtractedObjectShapeKeys:
    offsets_hash: str = ''
    scale_hash: str = ''
    vertex_ids_hash: str = ''
    vertex_offsets_hash: str = ''
    vertex_count: int = 0
    shapekey_count: int = 0
    batches: list[ExtractedObjectShapeKeysBatch] = field(default_factory=list)
    # Deprecated
    dispatch_y: int = 0
    checksum: int = 0

    def __post_init__(self):
        # Fill shapekeys batch object data for old Metadata.json file
        # Since earlier dumps had 1 batch only, it's perfectly safe to do
        if not self.batches and self.checksum > 0:
            self.batches = [ExtractedObjectShapeKeysBatch(
                dispatch_y=self.dispatch_y,
                checksum=self.checksum,
            )]

class EnumEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Enum):
            return obj.value
        return super().default(obj)


@dataclass
class ExtractedObject:
    vb0_hash: str
    cb4_hash: str
    vertex_count: int
    index_count: int
    components: List[ExtractedObjectComponent]
    shapekeys: ExtractedObjectShapeKeys
    export_format: Dict[str, ExtractedObjectBuffer]

    def as_json(self):
        return json.dumps(asdict(self), indent=4, cls=EnumEncoder)
    

def from_dict(cls, data):
    if not is_dataclass(cls):
        return data

    kwargs = {}
    for f in fields(cls):
        value = data.get(f.name)
        if value is None:
            kwargs[f.name] = None
            continue

        field_type = f.type
        origin = get_origin(field_type)

        if origin is list:
            item_type = get_args(field_type)[0]
            kwargs[f.name] = [from_dict(item_type, v) for v in value]
        elif origin is dict:
            key_type, val_type = get_args(field_type)
            kwargs[f.name] = {k: from_dict(val_type, v) for k, v in value.items()}
        else:
            kwargs[f.name] = from_dict(field_type, value)

    return cls(**kwargs)


def read_metadata(metadata_path: Path) -> ExtractedObject:
    with open(metadata_path) as f:
        return from_dict(ExtractedObject, json.load(f))
