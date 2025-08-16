import os
import sys
import time
import json
import shutil

from pathlib import Path
from typing import Dict
from dataclasses import dataclass
from collections import OrderedDict

from ..addon.exceptions import ConfigError

from ..migoto_io.blender_interface.utility import *

from ..migoto_io.data_model.dxgi_format import DXGIFormat
from ..migoto_io.data_model.byte_buffer import BufferLayout, BufferSemantic, AbstractSemantic, Semantic, ByteBuffer

from ..migoto_io.dump_parser.filename_parser import ShaderType, SlotType, SlotId
from ..migoto_io.dump_parser.dump_parser import Dump
from ..migoto_io.dump_parser.resource_collector import Source
from ..migoto_io.dump_parser.calls_collector import ShaderMap, Slot
from ..migoto_io.dump_parser.data_collector import DataMap, DataCollector

from .data_extractor import DataExtractor
from .shapekey_builder import ShapeKeyBuilder
from .component_builder import ComponentBuilder
from .output_builder import OutputBuilder, TextureFilter, ObjectData


@dataclass
class Configuration:
    # output_path: str
    # dump_dir_path: str
    shader_data_pattern: Dict[str, ShaderMap]
    shader_resources: Dict[str, DataMap]
    output_vb_layout: BufferLayout


# In WuWa VB is dynamically calculated by dedicated compute shaders (aka Pose CS)
# So mesh is getting rendered via following chain:
#               BONES -v  COLOR+TEXCOORD -v
#   BLEND+NORM+POS -> Pose CS -> VB -> VS & PS -> RENDER_TARGET
#    SHAPEKEY_OFFSETS -^            IB -^    ^- Textures
#                ^- Shape Keys Application CS Chain
#   SHAPEKEY_BUFFERS -^
#
# So we can grab all relevant data in 3 steps:
#   1. Collect VS>PS calls from dump
#   2. Collect CS calls from dump that output VB to #1 calls (cs-u0 and cs-u1 to vb)
#   3. For each unique VB output (cs-u0 & cs-u1) from #2 calls:
#        3.1. [BLEND+NORM+POS] Collect CS calls from #2 with VB as output (cs-u0 & cs-u1)
#        3.2. [VERT_COLOR_GROUPS] Collect PS calls from dump with output to #3.1 calls (cs-u0 to cs-t3)
#        3.3. [COLOR+TEXCOORD+IB+Textures] Collect VS>PS calls from #1 with VB as input (vb from cs-u0 and cs-u1)
#
configuration = Configuration(
    # output_path=r'C:\Projects\Wuthering Waves\3DMIGOTO_DEV\!PROJECTS\Collect',
    # dump_dir_path=r'C:\Projects\Wuthering Waves\3DMIGOTO_DEV\FrameAnalysis-2024-06-14-120528',
    # dump_dir_path=r'C:\Projects\Wuthering Waves\3DMIGOTO_DEV\FrameAnalysis-2024-06-10-190045',
    shader_data_pattern={
        'SHAPEKEY_CS_0': ShaderMap(ShaderType.Compute,
                                   inputs=[],
                                   outputs=[Slot('SHAPEKEY_CS_1', ShaderType.Empty, SlotType.UAV, SlotId(0))]),
        'SHAPEKEY_CS_1': ShaderMap(ShaderType.Compute,
                                   inputs=[Slot('SHAPEKEY_CS_0', ShaderType.Empty, SlotType.UAV, SlotId(1))],
                                   outputs=[Slot('SHAPEKEY_CS_2', ShaderType.Empty, SlotType.UAV, SlotId(0))]),
        'SHAPEKEY_CS_2': ShaderMap(ShaderType.Compute,
                                   inputs=[Slot('SHAPEKEY_CS_1', ShaderType.Empty, SlotType.UAV, SlotId(0))],
                                   outputs=[Slot('DRAW_VS_DUMMY', ShaderType.Empty, SlotType.UAV, SlotId(0))]),
        'DRAW_VS_DUMMY': ShaderMap(ShaderType.Vertex,
                             inputs=[Slot('SHAPEKEY_CS_2', ShaderType.Empty, SlotType.VertexBuffer, SlotId(6)),],
                             outputs=[]),
        'DRAW_VS': ShaderMap(ShaderType.Vertex,
                             # Hack: When shader is short cirquited on itself, calls with listed input slots will be excluded from resulting branch
                             inputs=[],
                             # Hack: Short cirquit shader on itself to allow search of shaders without outputs
                             outputs=[Slot('DRAW_VS', ShaderType.Empty, SlotType.VertexBuffer, SlotId(5))],),
    },
    shader_resources={
        'SHAPEKEY_OFFSET_BUFFER': DataMap([
                Source('SHAPEKEY_CS_1', ShaderType.Compute, SlotType.ConstantBuffer, SlotId(0)),
            ],
            BufferLayout([
                BufferSemantic(AbstractSemantic(Semantic.RawData), DXGIFormat.R32_UINT),
            ])),
        'SHAPEKEY_VERTEX_ID_BUFFER': DataMap([
                Source('SHAPEKEY_CS_1', ShaderType.Compute, SlotType.Texture, SlotId(0)),
            ],
            BufferLayout([
                BufferSemantic(AbstractSemantic(Semantic.RawData), DXGIFormat.R32_UINT),
            ])),
        'SHAPEKEY_VERTEX_OFFSET_BUFFER': DataMap([
                Source('SHAPEKEY_CS_1', ShaderType.Compute, SlotType.Texture, SlotId(1)),
            ],
            BufferLayout([
                BufferSemantic(AbstractSemantic(Semantic.RawData), DXGIFormat.R16G16B16_FLOAT),
            ])),

        'SHAPEKEY_OUTPUT': DataMap([Source('SHAPEKEY_CS_1', ShaderType.Empty, SlotType.UAV, SlotId(0))]),
        'SHAPEKEY_SCALE_OUTPUT': DataMap([Source('SHAPEKEY_CS_1', ShaderType.Empty, SlotType.UAV, SlotId(1))]),


        'SHAPEKEY_INPUT': DataMap([Source('DRAW_VS', ShaderType.Empty, SlotType.VertexBuffer, SlotId(6), ignore_missing=True)]),

        'POSE_INPUT_0': DataMap([Source('DRAW_VS', ShaderType.Empty, SlotType.VertexBuffer, SlotId(0))]),

        'SKELETON_DATA': DataMap([Source('DRAW_VS', ShaderType.Vertex, SlotType.ConstantBuffer, SlotId(4))]),

        'SKELETON_DATA_BUFFER': DataMap([
                Source('DRAW_VS', ShaderType.Vertex, SlotType.ConstantBuffer, SlotId(4)),
            ],
            BufferLayout(
                semantics=[
                    BufferSemantic(AbstractSemantic(Semantic.RawData, 0), DXGIFormat.R32_FLOAT, stride=48),
                ],
                force_stride=True)),

        'SKELETON_DATA_CB3': DataMap([Source('DRAW_VS', ShaderType.Vertex, SlotType.ConstantBuffer, SlotId(3))]),

        'SKELETON_DATA_BUFFER_CB3': DataMap([
                Source('DRAW_VS', ShaderType.Vertex, SlotType.ConstantBuffer, SlotId(3)),
            ],
            BufferLayout(
                semantics=[
                    BufferSemantic(AbstractSemantic(Semantic.RawData, 0), DXGIFormat.R32_FLOAT, stride=48),
                ],
                force_stride=True)),

        'POSE_CB': DataMap([
                Source('DRAW_VS', ShaderType.Vertex, SlotType.ConstantBuffer, SlotId(0)),
            ],
            BufferLayout([
                BufferSemantic(AbstractSemantic(Semantic.RawData), DXGIFormat.R32G32B32A32_UINT)
            ])),

        'IB_BUFFER_TXT': DataMap([
                Source('DRAW_VS', ShaderType.Empty, SlotType.IndexBuffer, file_ext='txt')
            ],
            BufferLayout([
                BufferSemantic(AbstractSemantic(Semantic.Index, 0), DXGIFormat.R16G16B16_UINT),
            ])
        ),

        'POSITION_BUFFER': DataMap([
                Source('DRAW_VS', ShaderType.Empty, SlotType.VertexBuffer, SlotId(0)),
            ],
            BufferLayout([
                BufferSemantic(AbstractSemantic(Semantic.Position, 0), DXGIFormat.R32G32B32_FLOAT),
            ])),
        'VECTOR_BUFFER': DataMap([
                Source('DRAW_VS', ShaderType.Empty, SlotType.VertexBuffer, SlotId(1)),
            ],
            BufferLayout([
                BufferSemantic(AbstractSemantic(Semantic.Tangent, 0), DXGIFormat.R8G8B8A8_SNORM),
                BufferSemantic(AbstractSemantic(Semantic.Normal, 0), DXGIFormat.R8G8B8A8_SNORM),
            ])),
        'TEXCOORD_BUFFER': DataMap([
                Source('DRAW_VS', ShaderType.Empty, SlotType.VertexBuffer, SlotId(2), file_ext='buf'),
            ],
            BufferLayout([
                BufferSemantic(AbstractSemantic(Semantic.TexCoord, 0), DXGIFormat.R16G16_FLOAT),
                BufferSemantic(AbstractSemantic(Semantic.Color, 1), DXGIFormat.R16G16_UNORM),
                BufferSemantic(AbstractSemantic(Semantic.TexCoord, 1), DXGIFormat.R16G16_FLOAT),
                BufferSemantic(AbstractSemantic(Semantic.TexCoord, 2), DXGIFormat.R16G16_FLOAT),
            ])),
        'TEXCOORD_BUFFER_STATIC': DataMap([
                Source('DRAW_VS', ShaderType.Empty, SlotType.VertexBuffer, SlotId(2), file_ext='buf'),
            ],
            BufferLayout([
                BufferSemantic(AbstractSemantic(Semantic.TexCoord, 0), DXGIFormat.R16G16_FLOAT),
                BufferSemantic(AbstractSemantic(Semantic.TexCoord, 1), DXGIFormat.R16G16_FLOAT),
            ])),
        'COLOR_BUFFER': DataMap([
                Source('DRAW_VS', ShaderType.Empty, SlotType.VertexBuffer, SlotId(3), file_ext='buf'),
            ],
            BufferLayout([
                BufferSemantic(AbstractSemantic(Semantic.Color, 0), DXGIFormat.R8G8B8A8_UNORM),
            ])),
        'BLEND_BUFFER': DataMap([
                Source('DRAW_VS', ShaderType.Empty, SlotType.VertexBuffer, SlotId(4)),
            ],
            BufferLayout([
                BufferSemantic(AbstractSemantic(Semantic.Blendindices, 0), DXGIFormat.R8G8B8A8_UINT),
                BufferSemantic(AbstractSemantic(Semantic.Blendweight, 0), DXGIFormat.R8G8B8A8_UNORM),
            ], force_stride=True)),
        'BLEND_BUFFER_WIDE': DataMap([
                Source('DRAW_VS', ShaderType.Empty, SlotType.VertexBuffer, SlotId(4)),
            ],
            BufferLayout([
                BufferSemantic(AbstractSemantic(Semantic.Blendindices, 0), DXGIFormat.R8_UINT, stride=8),
                BufferSemantic(AbstractSemantic(Semantic.Blendweight, 0), DXGIFormat.R8_UNORM, stride=8),
            ], force_stride=True)),
        
        'TEXTURE_0': DataMap([Source('DRAW_VS', ShaderType.Pixel, SlotType.Texture, SlotId(0), ignore_missing=True)]),
        'TEXTURE_1': DataMap([Source('DRAW_VS', ShaderType.Pixel, SlotType.Texture, SlotId(1), ignore_missing=True)]),
        'TEXTURE_2': DataMap([Source('DRAW_VS', ShaderType.Pixel, SlotType.Texture, SlotId(2), ignore_missing=True)]),
        'TEXTURE_3': DataMap([Source('DRAW_VS', ShaderType.Pixel, SlotType.Texture, SlotId(3), ignore_missing=True)]),
        'TEXTURE_4': DataMap([Source('DRAW_VS', ShaderType.Pixel, SlotType.Texture, SlotId(4), ignore_missing=True)]),
        'TEXTURE_5': DataMap([Source('DRAW_VS', ShaderType.Pixel, SlotType.Texture, SlotId(5), ignore_missing=True)]),
        'TEXTURE_6': DataMap([Source('DRAW_VS', ShaderType.Pixel, SlotType.Texture, SlotId(6), ignore_missing=True)]),
        'TEXTURE_7': DataMap([Source('DRAW_VS', ShaderType.Pixel, SlotType.Texture, SlotId(7), ignore_missing=True)]),
        'TEXTURE_8': DataMap([Source('DRAW_VS', ShaderType.Pixel, SlotType.Texture, SlotId(8), ignore_missing=True)]),
        
    },
    output_vb_layout=BufferLayout([
        BufferSemantic(AbstractSemantic(Semantic.Position, 0), DXGIFormat.R32G32B32_FLOAT),
        BufferSemantic(AbstractSemantic(Semantic.Tangent, 0), DXGIFormat.R8G8B8A8_SNORM),
        BufferSemantic(AbstractSemantic(Semantic.Normal, 0), DXGIFormat.R8G8B8A8_SNORM),
        BufferSemantic(AbstractSemantic(Semantic.Blendindices, 0), DXGIFormat.R8G8B8A8_UINT),
        BufferSemantic(AbstractSemantic(Semantic.Blendweight, 0), DXGIFormat.R8G8B8A8_UNORM),
        BufferSemantic(AbstractSemantic(Semantic.Color, 0), DXGIFormat.R8G8B8A8_UNORM),
        BufferSemantic(AbstractSemantic(Semantic.TexCoord, 0), DXGIFormat.R16G16_FLOAT),
        BufferSemantic(AbstractSemantic(Semantic.Color, 1), DXGIFormat.R16G16_UNORM),
        BufferSemantic(AbstractSemantic(Semantic.TexCoord, 1), DXGIFormat.R16G16_FLOAT),
        BufferSemantic(AbstractSemantic(Semantic.TexCoord, 2), DXGIFormat.R16G16_FLOAT),
    ]),
)


def write_objects(output_directory, objects: Dict[str, ObjectData], allow_missing_shapekeys = False):
    output_directory = Path(output_directory)

    output_directory.mkdir(parents=True, exist_ok=True)

    for object_hash, object_data in objects.items():
        object_name = object_hash

        if object_data.shapekeys.offsets_hash and not object_data.shapekeys.shapekey_offsets:
            if allow_missing_shapekeys:
                object_name += '_MISSING_SHAPEKEYS'
            else:
                continue

        object_directory = output_directory / object_name
        object_directory.mkdir(parents=True, exist_ok=True)

        textures = {}
        texture_usage = {}
        
        for component_id, component in enumerate(object_data.components):

            component_filename = f'Component {component_id}'

            # Write buffers
            with open(object_directory / f'{component_filename}.ib', "wb") as f:
                f.write(component.ib)
            with open(object_directory / f'{component_filename}.vb', "wb") as f:
                f.write(component.vb)
            with open(object_directory / f'{component_filename}.fmt', "w") as f:
                f.write(component.fmt)

            # Write textures
            texture_usage[component_filename] = OrderedDict()
            for texture in component.textures:

                if texture.hash not in textures:
                    textures[texture.hash] = {
                        'path': texture.path,
                        'components': []
                    }

                textures[texture.hash]['components'].append(str(component_id))

                if texture.get_slot() not in texture_usage[component_filename]:
                    texture_usage[component_filename][texture.get_slot()] = []

                shaders = '-'.join([shader.raw for shader in texture.shaders])
                texture_usage[component_filename][texture.get_slot()].append(f'{texture.hash}-{shaders}')
                
            texture_usage[component_filename] = OrderedDict(sorted(texture_usage[component_filename].items()))

        for texture_hash, texture in textures.items():
            path = Path(texture['path'])
            components = '-'.join(sorted(list(set(texture['components']))))
            shutil.copyfile(path, object_directory / f'Components-{components} t={texture_hash}{path.suffix}')
            
        with open(object_directory / f'TextureUsage.json', "w") as f:
            f.write(json.dumps(texture_usage, indent=4))

        with open(object_directory / f'Metadata.json', "w") as f:
            f.write(object_data.metadata)


def extract_frame_data(cfg):

    start_time = time.time()

    dump_path = resolve_path(cfg.frame_dump_folder)

    if not dump_path.is_dir():
        raise ConfigError('frame_dump_folder', 'Specified dump folder does not exist!')
    if not Path(dump_path / 'log.txt').is_file():
        raise ConfigError('frame_dump_folder', 'Specified dump folder is missing log.txt file!')
    
    # Create data model of the frame dump
    dump = Dump(
        dump_directory=dump_path
    )

    # Get data view from dump data model
    frame_data = DataCollector(
        dump=dump,
        shader_data_pattern=configuration.shader_data_pattern,
        shader_resources=configuration.shader_resources
    )

    # Extract mesh objects data from data view
    data_extractor = DataExtractor(
        call_branches=frame_data.call_branches
    )

    # Build shape keys index from byte buffers
    shapekeys = ShapeKeyBuilder(
        shapekey_data=data_extractor.shape_key_data
    )

    # Build components from byte buffers
    component_builder = ComponentBuilder(
        output_vb_layout=configuration.output_vb_layout,
        shader_hashes=data_extractor.shader_hashes,
        shapekeys=shapekeys.shapekeys,
        draw_data=data_extractor.draw_data
    )

    # Build output data object
    output_builder = OutputBuilder(
        shapekeys=shapekeys.shapekeys,
        mesh_objects=component_builder.mesh_objects,
        texture_filter=TextureFilter(
            min_file_size=cfg.skip_small_textures_size*1024 if cfg.skip_small_textures else 0,
            exclude_extensions=['jpg'] if cfg.skip_jpg_textures else [],
            exclude_same_slot_hash_textures=cfg.skip_same_slot_hash_textures,
        )
    )

    write_objects(resolve_path(cfg.extract_output_folder), output_builder.objects, cfg.allow_missing_shapekeys)

    print(f"Execution time: %s seconds" % (time.time() - start_time))

    return output_builder


def get_dir_path():
    dir_path = ""

    if len(sys.argv) > 1:
        dir_path = sys.argv[1]

    if not os.path.exists(dir_path):
        print('Enter the name of frame dump folder:')
        dir_path = input()

    dir_path = os.path.abspath(dir_path)

    if not os.path.exists(dir_path):
        raise ValueError(f'Folder not found: {dir_path}!')
    if not os.path.isdir(dir_path):
        raise ValueError(f'Not a folder: {dir_path}!')

    return dir_path


if __name__ == "__main__":
    # try:
    extract_frame_data(configuration.dump_dir_path, configuration.output_path)
    # except Exception as e:
    #     print(f'Error: {e}')
    #     input()
