from dataclasses import dataclass, field

from typing import List, Dict

from ..migoto_io.data_model.dxgi_format import DXGIFormat
from ..migoto_io.data_model.byte_buffer import ByteBuffer, BufferLayout, BufferSemantic, AbstractSemantic, Semantic

from .data_extractor import ShapeKeyData, DrawData


@dataclass
class ShapeKeys:
    offsets_hash: str
    scale_hash: str = ''
    dispatch_y: int = 0
    shapekey_offsets: list = field(default_factory=lambda: [])
    # ShapeKey ID based indexed list of {VertexID: VertexOffsets}
    shapekeys_index: List[Dict[int, List[float]]] = field(default_factory=lambda: [])
    # Vertex ID based indexed dict of {ShapeKeyID: VertexOffsets}
    indexed_shapekeys: Dict[int, Dict[int, List[float]]] = field(default_factory=lambda: {})

    def get_shapekey_ids(self, vertex_offset, vertex_count):
        """
        Returns sorted list of shapekey ids applied to provided range of vertices
        """
        shapekey_ids = []
        for vertex_id in range(vertex_offset, vertex_offset + vertex_count):
            shapekeys = self.indexed_shapekeys.get(vertex_id, None)
            if shapekeys is None:
                continue
            for shapekey_id in shapekeys.keys():
                if shapekey_id not in shapekey_ids:
                    shapekey_ids.append(shapekey_id)
        shapekey_ids.sort()
        return shapekey_ids

    def build_shapekey_buffer(self, vertex_offset, vertex_count):
        """
        Returns Blender-importable ByteBuffer for shapekeys within provided range of vertices
        """
        shapekey_ids = self.get_shapekey_ids(vertex_offset, vertex_count)

        if len(shapekey_ids) == 0:
            return None

        layout = BufferLayout([
            BufferSemantic(AbstractSemantic(Semantic.ShapeKey, shapekey_id), DXGIFormat.R16G16B16_FLOAT)
            for shapekey_id in shapekey_ids
        ])

        shapekey_buffer = ByteBuffer(layout)
        shapekey_buffer.extend(vertex_count)

        for vertex_id in range(vertex_offset, vertex_offset + vertex_count):
            indexed_vertex_shapekeys = self.indexed_shapekeys.get(vertex_id, None)
            element_id = vertex_id - vertex_offset
            for semantic in shapekey_buffer.layout.semantics:
                shapekey_id = semantic.abstract.index
                if indexed_vertex_shapekeys is None or shapekey_id not in indexed_vertex_shapekeys:
                    shapekey_buffer.get_element(element_id).set_value(semantic, [0, 0, 0])
                else:
                    shapekey_buffer.get_element(element_id).set_value(semantic, indexed_vertex_shapekeys[shapekey_id])

        return shapekey_buffer


@dataclass
class ShapeKeyBuilder:
    # Input
    shapekey_data: Dict[str, ShapeKeyData]
    # Output
    shapekeys: Dict[str, ShapeKeys] = field(init=False)

    def __post_init__(self):
        self.shapekeys = {}

        for shapekey_hash, shapekey_data in self.shapekey_data.items():

            shapekey_offsets = shapekey_data.shapekey_offset_buffer.get_values(AbstractSemantic(Semantic.RawData))[0:128]
            vertex_ids = shapekey_data.shapekey_vertex_id_buffer.get_values(AbstractSemantic(Semantic.RawData))
            vertex_offsets = shapekey_data.shapekey_vertex_offset_buffer.get_values(AbstractSemantic(Semantic.RawData))

            # Detect last non-zero entry in the vertex_offsets buffer consisting of 3 floats and 3 zeroes per row
            # vertex_offsets_len = int(len(vertex_offsets) / 6)
            # last_data_entry_id = vertex_offsets_len - 1
            # for entry_id in reversed(range(vertex_offsets_len)):
            #     vertex_offset = vertex_offsets[entry_id * 6:entry_id * 6 + 6]
            #     if any(v != 0 for v in vertex_offset):
            #         break
            #     last_data_entry_id = entry_id

            # Original buffer doesn't contain offset for 129th group, but we'll need it for the loop below
            # last_shapekey_offset = shapekey_offsets[-1]
            # if last_shapekey_offset > last_data_entry_id:
            #     shapekey_offsets.append(last_shapekey_offset)
            # else:
            #     shapekey_offsets.append(last_data_entry_id + 1)

            last_data_entry_id = shapekey_offsets[-1]

            # Process shapekey entries, we'll build both VertexID and ShapeKeyID based outputs for fast indexing
            shapekeys_index = []
            indexed_shapekeys = {}
            for shapekey_id, first_entry_id in enumerate(shapekey_offsets):
                # Stop processing if next entries have no data
                if first_entry_id >= last_data_entry_id:
                    break
                # Process all entries from current shapekey offset 'till offset of the next shapekey
                entries = {}
                for entry_id in range(first_entry_id, shapekey_offsets[shapekey_id + 1]):
                    vertex_id = vertex_ids[entry_id]
                    vertex_offset = vertex_offsets[entry_id * 6:entry_id * 6 + 3]
                    entries[vertex_id] = vertex_offset
                    if vertex_id not in indexed_shapekeys:
                        indexed_shapekeys[vertex_id] = {}
                    indexed_shapekeys[vertex_id][shapekey_id] = vertex_offset
                shapekeys_index.append(entries)

            self.shapekeys[shapekey_hash] = ShapeKeys(
                offsets_hash=shapekey_data.shapekey_hash,
                scale_hash=shapekey_data.shapekey_scale_hash,
                dispatch_y=shapekey_data.dispatch_y,
                shapekey_offsets=shapekey_offsets,
                shapekeys_index=shapekeys_index,
                indexed_shapekeys=indexed_shapekeys,
            )
