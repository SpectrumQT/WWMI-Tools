import os
import numpy
import time
import re
import bpy

from pathlib import Path

from bpy_extras.io_utils import axis_conversion

from ..addon.exceptions import ConfigError

from ..migoto_io.blender_interface.utility import *
from ..migoto_io.blender_interface.collections import *
from ..migoto_io.blender_interface.objects import *
from ..migoto_io.data_model.data_model import DataModel
from ..migoto_io.data_model.byte_buffer import NumpyBuffer, MigotoFmt

from ..extract_frame_data.metadata_format import read_metadata


# TODO: Add support of import of unhandled semantics into vertex attributes
class ObjectImporter:

    def import_object(self, operator, context, cfg):

        object_source_folder = resolve_path(cfg.object_source_folder)

        if not object_source_folder.is_dir():
            raise ConfigError('object_source_folder', 'Specified sources folder does not exist!')

        start_time = time.time()
        print(f"Object import started for '{object_source_folder.stem}' folder")

        imported_objects = []
        
        for filename in os.listdir(object_source_folder):
            if not filename.endswith('fmt'):
                continue

            fmt_path = object_source_folder / filename
            ib_path = fmt_path.with_suffix('.ib')
            vb_path = fmt_path.with_suffix('.vb')

            if not ib_path.is_file():
                raise ConfigError('object_source_folder', f'Specified folder is missing .fmt file for {fmt_path.stem}!')
            if not vb_path.is_file():
                raise ConfigError('object_source_folder', f'Specified folder is missing .fmt file for {fmt_path.stem}!')

            obj = self.import_component(operator, context, cfg, fmt_path, ib_path, vb_path)

            # from .import_old import import_3dmigoto_vb_ib
            # obj = import_3dmigoto_vb_ib(operator, context, cfg, [((vb_path, fmt_path), (ib_path, fmt_path), True, None)], flip_mesh=cfg.mirror_mesh, flip_winding=True)
            
            imported_objects.append(obj)
        
        if len(imported_objects) == 0:
            raise ConfigError('object_source_folder', 'Specified folder is missing .fmt files for components!')

        col = new_collection(object_source_folder.stem)
        for obj in imported_objects:
            link_object_to_collection(obj, col)

        print(f'Total import time: {time.time() - start_time :.3f}s')

    def import_component(self, operator, context, cfg, fmt_path: Path, ib_path: Path, vb_path: Path, axis_forward='Y', axis_up='Z'):

        start_time = time.time()

        with open(fmt_path, 'r') as fmt, open(ib_path, 'rb') as ib, open(vb_path, 'rb') as vb:
            migoto_fmt = MigotoFmt(fmt)

            index_buffer = NumpyBuffer(migoto_fmt.ib_layout)
            index_buffer.import_raw_data(ib.read())

            vertex_buffer = NumpyBuffer(migoto_fmt.vb_layout)
            vertex_buffer.import_raw_data(vb.read())

            object_source_folder = resolve_path(cfg.object_source_folder)
            try:
                extracted_object = read_metadata(object_source_folder / 'Metadata.json')
            except FileNotFoundError:
                raise ConfigError('object_source_folder', 'Specified folder is missing Metadata.json!')
            except Exception as e:
                raise ConfigError('object_source_folder', f'Failed to load Metadata.json:\n{e}')
            
            vg_remap = None
            if cfg.import_skeleton_type == 'MERGED':
                component_pattern = re.compile(r'.*component[ -_]*([0-9]+).*')
                result = component_pattern.findall(fmt_path.name.lower())
                if len(result) == 1:
                    component = extracted_object.components[int(result[0])]
                    vg_remap = numpy.array(list(component.vg_map.values()))

            mesh = bpy.data.meshes.new(fmt_path.stem)
            obj = bpy.data.objects.new(mesh.name, mesh)

            global_matrix = axis_conversion(from_forward=axis_forward, from_up=axis_up).to_4x4()
            obj.matrix_world = global_matrix

            model = DataModel()
            model.flip_winding = True
            model.flip_texcoord_v = True
            model.legacy_vertex_colors = cfg.color_storage == 'LEGACY'

            model.set_data(obj, mesh, index_buffer, vertex_buffer, vg_remap, mirror_mesh=cfg.mirror_mesh, mesh_scale=0.01, mesh_rotation=(0, 0, 180))

            num_shapekeys = 0 if obj.data.shape_keys is None else len(getattr(obj.data.shape_keys, 'key_blocks', []))

            print(f'{fmt_path.stem} import time: {time.time()-start_time :.3f}s ({len(obj.data.vertices)} vertices, {len(obj.data.loops)} indices, {num_shapekeys} shapekeys)')

            return obj


def blender_import(operator, context, cfg):
    object_importer = ObjectImporter()
    object_importer.import_object(operator, context, cfg)
