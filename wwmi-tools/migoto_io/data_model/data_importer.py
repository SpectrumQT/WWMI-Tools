import numpy
import bpy

from typing import List, Tuple, Dict, Optional

from .byte_buffer import AbstractSemantic, Semantic, BufferSemantic, NumpyBuffer, BufferLayout
from .dxgi_format import DXGIFormat, DXGIType


class BlenderDataImporter:

    def set_data(self,
                 obj: bpy.types.Object, 
                 mesh: bpy.types.Mesh, 
                 index_buffer: NumpyBuffer,
                 vertex_buffer: NumpyBuffer,
                 semantic_converters: Dict[AbstractSemantic, List[callable]], 
                 format_converters: Dict[AbstractSemantic, List[callable]],
                 legacy_vertex_colors: bool = False):
        
        buffer_semantic = index_buffer.layout.get_element(AbstractSemantic(Semantic.Index))
        index_data = self.get_semantic_data(index_buffer, buffer_semantic, format_converters, semantic_converters)

        self.import_faces(mesh, index_data)

        vertex_ids = index_data.flatten()

        mesh.vertices.add(len(vertex_buffer.data))

        vg_indices = {}
        vg_weights = {}
        texcoords = {}
        shapekeys = {}
        normals = None
        
        for buffer_semantic in vertex_buffer.layout.semantics:
            semantic = buffer_semantic.abstract.enum

            # Skip tangents import, we'll recalc them on export
            if semantic in [Semantic.Tangent, Semantic.BitangentSign]:
                continue

            # Get converted data from vertex buffer
            data = self.get_semantic_data(vertex_buffer, buffer_semantic, format_converters, semantic_converters)

            if semantic == Semantic.ShapeKey:
                shapekeys[buffer_semantic.abstract.index] = data
            elif semantic == Semantic.Color:
                self.import_colors(mesh, buffer_semantic.get_name(), data, vertex_ids, legacy_vertex_colors)
            elif semantic == Semantic.TexCoord:
                texcoords[buffer_semantic.abstract.index] = data
            elif semantic == Semantic.Normal:
                normals = data
            elif semantic == Semantic.Blendindices:
                vg_indices[buffer_semantic.abstract.index] = data
            elif semantic == Semantic.Blendweight:
                vg_weights[buffer_semantic.abstract.index] = data
            elif semantic == Semantic.Position:
                self.import_positions(mesh, data)
            else:
                continue

        self.import_texcoords(mesh, texcoords, vertex_ids)
        self.import_vertex_groups(obj, vg_indices, vg_weights)
        self.import_shapekeys(obj, shapekeys)

        # Create edges and other missing metadata
        mesh.validate(verbose=False, clean_customdata=False)
        mesh.update()

        self.import_normals(mesh, normals, vertex_ids)

    def get_semantic_data(self, 
                          buffer: NumpyBuffer, 
                          buffer_semantic: BufferSemantic, 
                          format_converters: Dict[AbstractSemantic, List[callable]], 
                          semantic_converters: Dict[AbstractSemantic, List[callable]]):
        
        data = buffer.get_field(buffer_semantic.get_name())
    
        for converter in format_converters.get(buffer_semantic.abstract, []):
            try:
                data = converter(data)
            except ValueError:
                if not data.flags.writeable:
                    data = converter(data.copy())

        # Any remaining normalized integers must be converted to floats before running semantic converters
        if buffer_semantic.format.dxgi_type in [DXGIType.UNORM16, DXGIType.UNORM8, DXGIType.SNORM16, DXGIType.SNORM8]:
            if not numpy.issubdtype(data.dtype, numpy.floating):
                data = buffer_semantic.format.type_decoder(data)
            
        for converter in semantic_converters.get(buffer_semantic.abstract, []):
            try:
                data = converter(data)
            except ValueError:
                if not data.flags.writeable:
                    data = converter(data.copy())

        return data
   
    def import_faces(self, 
                     mesh: bpy.types.Mesh, 
                     index_data: numpy.ndarray):
        
        mesh.loops.add(len(index_data) * 3)
        mesh.polygons.add(len(index_data))

        mesh.loops.foreach_set('vertex_index', index_data.flatten())

        mesh.polygons.foreach_set('loop_start', [x*3 for x in range(len(index_data))])
        mesh.polygons.foreach_set('loop_total', [3] * len(index_data))

    def import_positions(self, 
                         mesh: bpy.types.Mesh, 
                         position_data: numpy.ndarray):
        
        mesh.vertices.foreach_set('co', position_data.ravel())
        
    def import_vertex_groups(self, 
                             obj: bpy.types.Object, 
                             semantic_vg_indices: Dict[int, numpy.ndarray], 
                             semantic_vg_weights: Dict[int, numpy.ndarray]):
        
        assert (len(semantic_vg_indices) == len(semantic_vg_weights))

        vg_index_offset = 0

        for semantic_index in sorted(semantic_vg_indices.keys()):

            vg_indices = semantic_vg_indices[semantic_index]
            vg_weights = semantic_vg_weights[semantic_index]

            assert (len(vg_indices) == len(vg_weights))

            num_vertex_groups = vg_indices.max()

            semantic_prefix = '' if semantic_index == 0 else f'{semantic_index}_'
            
            for i in range(num_vertex_groups + 1):
                obj.vertex_groups.new(name=semantic_prefix+str(i))

            for vertex_id, (indices, weights) in enumerate(zip(vg_indices, vg_weights)):
                for index, weight in zip(indices, weights):
                    if weight == 0.0:
                        continue
                    obj.vertex_groups[vg_index_offset+index].add((vertex_id,), weight, 'REPLACE')
            
            vg_index_offset += num_vertex_groups

    def import_colors(self, 
                      mesh: bpy.types.Mesh, 
                      color_name: str, 
                      color_data: numpy.ndarray, 
                      vertex_ids: numpy.ndarray,
                      legacy_vertex_colors: bool = False):
        
        if legacy_vertex_colors:
            mesh.vertex_colors.new(name=color_name)
            color_layer = mesh.vertex_colors[color_name].data
            color_layer.foreach_set('color', color_data[vertex_ids].flatten())
        else:
            color_attribute = mesh.color_attributes.new(name=color_name, type='FLOAT_COLOR', domain='CORNER')
            color_attribute.data.foreach_set('color', color_data[vertex_ids].flatten())

    def import_normals(self, 
                       mesh: bpy.types.Mesh, 
                       normals: Optional[numpy.ndarray], 
                       vertex_ids: numpy.ndarray):
        
        if normals is None:
            if hasattr(mesh, 'calc_normals'):
                mesh.calc_normals()
            return
        if bpy.app.version >= (4, 1):
            # Directly write vertex normals to loops without any shenanigans
            mesh.normals_split_custom_set_from_vertices(normals)
        else:
            # Initialize empty split vertex normals
            mesh.create_normals_split()
            # Write vertex normals, they will be immidiately converted to loop normals
            mesh.loops.foreach_set('normal', normals[vertex_ids].flatten().tolist())
            # Read loop normals
            recalculated_normals = numpy.empty(len(mesh.loops)*3, dtype=numpy.float32)
            mesh.loops.foreach_get('normal', recalculated_normals)
            recalculated_normals = recalculated_normals.reshape((-1, 3))
            # Force usage of custom normals
            mesh.use_auto_smooth = True
            # Force vertex normals interpolation across the polygon (required in older versions)
            mesh.polygons.foreach_set('use_smooth', numpy.ones(len(mesh.polygons), dtype=numpy.int8))
            # Write loop normals to permanent storage
            mesh.normals_split_custom_set(recalculated_normals.tolist())

    def import_texcoords(self, 
                         mesh: bpy.types.Mesh, 
                         texcoords: Dict[int, numpy.ndarray], 
                         vertex_ids: numpy.ndarray):
        
        if not texcoords:
            return
        
        for (texcoord_id, data) in sorted(texcoords.items()):
            uv_name = f'TEXCOORD{texcoord_id and texcoord_id or ""}.xy'
            mesh.uv_layers.new(name=uv_name)

            uv_layer = mesh.uv_layers[uv_name].data
            uv_layer.foreach_set('uv', data[vertex_ids].flatten())

    def import_shapekeys(self, 
                         obj: bpy.types.Object, 
                         shapekeys: Dict[int, numpy.ndarray]):
        
        if not shapekeys:
            return

        # Add basis shapekey
        basis = obj.shape_key_add(name='Basis')
        basis.interpolation = 'KEY_LINEAR'

        # Set shapekeys to relative 'cause WuWa uses this type
        obj.data.shape_keys.use_relative = True

        # Import shapekeys
        vert_count = len(obj.data.vertices)

        basis_co = numpy.empty(vert_count * 3, dtype=numpy.float32)
        basis.data.foreach_get('co', basis_co)
        basis_co = basis_co.reshape(-1, 3)  

        for shapekey_id, offsets in shapekeys.items():
            # Add new shapekey
            shapekey = obj.shape_key_add(name=f'Deform {shapekey_id}')
            shapekey.interpolation = 'KEY_LINEAR'

            if bpy.app.version >= (5, 0):
                # Blender 5.0 defaults shapekeys to 1.0 
                shapekey.value = 0

            position_offsets = numpy.array(offsets, dtype=numpy.float32).reshape(-1, 3)

            # Apply shapekey vertex position offsets
            position_offsets += basis_co

            shapekey.data.foreach_set('co', position_offsets.ravel())
