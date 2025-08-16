import hashlib

from dataclasses import dataclass, field
from typing import List, Dict
from pathlib import Path

from ..migoto_io.data_model.dxgi_format import DXGIFormat
from ..migoto_io.data_model.byte_buffer import Semantic, AbstractSemantic
from ..migoto_io.dump_parser.filename_parser import ResourceDescriptor

from .shapekey_builder import ShapeKeys
from .component_builder import MeshObject
from .metadata_format import ExtractedObject, ExtractedObjectComponent, ExtractedObjectShapeKeys, ExtractedObjectBuffer, ExtractedObjectBufferSemantic


@dataclass
class TextureFilter:
    min_file_size: int
    exclude_extensions: List[str]
    exclude_same_slot_hash_textures: bool


@dataclass
class ComponentData:
    fmt: str
    vb: bytearray
    ib: bytearray
    textures: Dict[str, List[ResourceDescriptor]]


@dataclass
class ObjectData:
    metadata: str
    components: List[ComponentData]
    shapekeys: ShapeKeys


@dataclass
class OutputBuilder:
    # Input
    shapekeys: Dict[str, ShapeKeys]
    mesh_objects: Dict[str, MeshObject]
    texture_filter: TextureFilter
    # Output
    objects: Dict[str, ObjectData] = field(init=False)

    def __post_init__(self):
        self.objects = {}
        for vb_hash, mesh_object in self.mesh_objects.items():

            shapekeys = self.shapekeys.get(mesh_object.shapekey_hash, ShapeKeys(offsets_hash=mesh_object.shapekey_hash or ''))

            self.filter_textures(mesh_object)

            self.objects[vb_hash] = ObjectData(
                metadata=self.build_metadata(mesh_object, shapekeys),
                components=[
                    ComponentData(
                        fmt=self.build_fmt(component.vertex_buffer, component.index_buffer),
                        vb=component.vertex_buffer.get_bytes(),
                        ib=component.index_buffer.get_bytes(),
                        textures=component.textures,
                    ) for component in mesh_object.components
                ],
                shapekeys=shapekeys
            )

    def filter_textures(self, mesh_object):

        garbage_list = [
            '980666bd245e94c32ee0ed46435b122d41ef3b7c13f9e389eb4d56916ab7f611',  # Stars mask
            '42daba7e8702346c175c69840d4530d6798f0a4e8e2504b0e9c5969fe3c8b5af',  # Golden Orb mask
            '99a43e3d7ef0ecf4cc5753ba306326a44d9b8006e4d0f0728d941fb02bd0774b',  # Gray Wave mask
            # '2e4e6aecbfdabc7b292a55e9dab133ed3d0192145b44f6ea72c19f9dbd2a9033',  # Eye mask
        ]

        num_slot_hash_entries = {}

        for component in mesh_object.components:

            for texture in component.textures.values():
                slot_hash = texture.get_slot_hash()

                if slot_hash not in num_slot_hash_entries:
                    num_slot_hash_entries[slot_hash] = 0

                num_slot_hash_entries[slot_hash] += 1

        for component in mesh_object.components:

            textures = []

            for texture in component.textures.values():

                # Exclude texture with ignored extension
                if len(self.texture_filter.exclude_extensions) > 0:
                    if texture.ext in self.texture_filter.exclude_extensions:
                        continue
                    
                # Exclude texture below minimal file size 
                if self.texture_filter.min_file_size != 0:
                    file_size = Path(texture.path).stat().st_size
                    if file_size < self.texture_filter.min_file_size:
                        continue

                # Exclude texture if it has same slot+hash in all components
                if self.texture_filter.exclude_same_slot_hash_textures:
                    num_components = len(mesh_object.components)
                    if num_components > 1:
                        slot_hash = texture.get_slot_hash()
                        if num_slot_hash_entries[slot_hash] == num_components:
                            continue

                # Exclude known garbage textures
                with open(texture.path, 'rb') as f:
                    data_hash = hashlib.sha256(f.read()).hexdigest()
                    if data_hash in garbage_list:
                        continue

                textures.append(texture)

            component.textures = textures

    @staticmethod
    def build_metadata(mesh_object: MeshObject, shapekeys):
        vertex_buffer_layout = next(iter(mesh_object.components)).vertex_buffer.layout

        vg_index_stride = vertex_buffer_layout.get_element(AbstractSemantic(Semantic.Blendindices)).stride
        vg_weight_stride = vertex_buffer_layout.get_element(AbstractSemantic(Semantic.Blendweight)).stride

        export_format = {
            'Index': ExtractedObjectBuffer([
                ExtractedObjectBufferSemantic(Semantic.Index, 0, DXGIFormat.R32_UINT, stride=12)
            ]),
            'Position': ExtractedObjectBuffer([
                ExtractedObjectBufferSemantic(Semantic.Position, 0, DXGIFormat.R32G32B32_FLOAT)
            ]),
            'Blend': ExtractedObjectBuffer([
                ExtractedObjectBufferSemantic(Semantic.Blendindices, 0, DXGIFormat.R8_UINT, stride=vg_index_stride),
                ExtractedObjectBufferSemantic(Semantic.Blendweight, 0, DXGIFormat.R8_UINT, stride=vg_weight_stride),
            ]),
            'Vector': ExtractedObjectBuffer([
                ExtractedObjectBufferSemantic(Semantic.Tangent, 0, DXGIFormat.R8G8B8A8_SNORM),
                ExtractedObjectBufferSemantic(Semantic.Normal, 0, DXGIFormat.R8G8B8_SNORM),
                ExtractedObjectBufferSemantic(Semantic.BitangentSign, 0, DXGIFormat.R8_SNORM),
            ]),
        }

        if vertex_buffer_layout.get_element(AbstractSemantic(Semantic.TexCoord, 2)):
            export_format.update({
                'Color': ExtractedObjectBuffer([
                    ExtractedObjectBufferSemantic(Semantic.Color, 0, DXGIFormat.R8G8B8A8_UNORM)
                ]),
                'TexCoord': ExtractedObjectBuffer([
                    ExtractedObjectBufferSemantic(Semantic.TexCoord, 0, DXGIFormat.R16G16_FLOAT),
                    ExtractedObjectBufferSemantic(Semantic.Color, 1, DXGIFormat.R16G16_UNORM),
                    ExtractedObjectBufferSemantic(Semantic.TexCoord, 1, DXGIFormat.R16G16_FLOAT),
                    ExtractedObjectBufferSemantic(Semantic.TexCoord, 2, DXGIFormat.R16G16_FLOAT),
                ])
            })
        else:
            export_format.update({
                'TexCoord': ExtractedObjectBuffer([
                    ExtractedObjectBufferSemantic(Semantic.TexCoord, 0, DXGIFormat.R16G16_FLOAT),
                    ExtractedObjectBufferSemantic(Semantic.TexCoord, 1, DXGIFormat.R16G16_FLOAT),
                ])
            })

        export_format.update({    
            'ShapeKeyOffset': ExtractedObjectBuffer([
                ExtractedObjectBufferSemantic(Semantic.ShapeKey, 0, DXGIFormat.R32G32B32A32_UINT)
            ]),
            'ShapeKeyVertexId': ExtractedObjectBuffer([
                ExtractedObjectBufferSemantic(Semantic.ShapeKey, 1, DXGIFormat.R32_UINT)
            ]),
            'ShapeKeyVertexOffset': ExtractedObjectBuffer([
                ExtractedObjectBufferSemantic(Semantic.ShapeKey, 2, DXGIFormat.R16_FLOAT)
            ]),
        })

        return ExtractedObject(

            vb0_hash=mesh_object.vb0_hash,
            cb4_hash=mesh_object.cb4_hash,
            vertex_count=mesh_object.vertex_count,
            index_count=mesh_object.index_count,

            components=[
                ExtractedObjectComponent(
                    vertex_offset=component.vertex_offset,
                    vertex_count=component.vertex_count,
                    index_offset=component.index_offset,
                    index_count=component.index_count,
                    vg_offset=component.vg_offset,
                    vg_count=component.vg_count,
                    vg_map=component.vg_map,
                ) for component in mesh_object.components
            ],

            shapekeys=ExtractedObjectShapeKeys(
                offsets_hash=shapekeys.offsets_hash,
                scale_hash=shapekeys.scale_hash,
                vertex_count=shapekeys.shapekey_offsets[-1] - 1,
                dispatch_y=shapekeys.dispatch_y,
                checksum=sum(shapekeys.shapekey_offsets[0:4]),
            ) if shapekeys.shapekey_offsets else ExtractedObjectShapeKeys(),

            export_format=export_format,

        ).as_json()

    @staticmethod
    def build_fmt(vb, ib):
        # Default 3dm blender import script expects 1-byte IB format DXGI_FORMAT_R16_UINT
        # Our IndexBuffer implementation uses 3-byte IB format DXGI_FORMAT_R16G16B16_UINT
        # So we'll have to override said format to be compatible
        ib_format = ib.get_format()
        if ib_format.find('16_UINT') != -1:
            ib_format = DXGIFormat.R16_UINT.get_format()
        elif ib_format.find('32_UINT') != -1:
            ib_format = DXGIFormat.R32_UINT.get_format()
        else:
            raise ValueError(f'unknown IB format {ib_format}')

        fmt = ''
        fmt += f'stride: {vb.layout.stride}\n'
        fmt += f'topology: trianglelist\n'
        fmt += f'format: {ib_format}\n'
        fmt += vb.layout.to_string()

        return fmt
