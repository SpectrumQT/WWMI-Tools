import collections
import copy
import numpy
import time
import bpy

from typing import List, Tuple, Dict, Optional
from operator import attrgetter, itemgetter

from .byte_buffer import AbstractSemantic, Semantic, BufferSemantic, NumpyBuffer, BufferLayout
from .dxgi_format import DXGIFormat, DXGIType


class BlenderDataExtractor:
    blender_data_formats: Dict[Semantic, DXGIFormat]
    blender_loop_semantics: List[Semantic] = [
        Semantic.Index, Semantic.VertexId, Semantic.Normal, Semantic.Tangent, Semantic.BitangentSign, Semantic.Color, Semantic.TexCoord
    ]
    blender_vertex_semantics: List[Semantic] = [
        Semantic.Position, Semantic.Blendindices, Semantic.Blendweight
    ]
    format_converters: Dict[AbstractSemantic, List[callable]] = {}
    semantic_converters: Dict[AbstractSemantic, List[callable]] = {}

    def get_data(self, 
                 mesh: bpy.types.Mesh, 
                 layout: BufferLayout, 
                 blender_data_formats: Dict[Semantic, DXGIFormat],
                 semantic_converters: Dict[AbstractSemantic, List[callable]], 
                 format_converters: Dict[AbstractSemantic, List[callable]],
                 vertex_ids_cache: Optional[numpy.ndarray] = None,
                 flip_winding= False) -> Tuple[numpy.ndarray, NumpyBuffer]:
        
        self.blender_data_formats = blender_data_formats
        
        # Initialize converters 
        for semantic, converter in self.semantic_converters.items():
            if semantic not in semantic_converters:
                semantic_converters[semantic] = converter
        for semantic, converter in self.format_converters.items():
            if semantic not in format_converters:
                format_converters[semantic] = converter

        layout.add_element(BufferSemantic(AbstractSemantic(Semantic.VertexId, 0), self.blender_data_formats[Semantic.VertexId]))
        proxy_layout = self.make_proxy_layout(layout, semantic_converters)

        if vertex_ids_cache is None:
            # Extract requested data from blender loop vertices
            loop_data, index_data = self.get_loop_data(mesh, proxy_layout, flip_winding=flip_winding, dedupe = True)
            vertex_ids = loop_data.get_field(AbstractSemantic(Semantic.VertexId).get_name())
        else:
            loop_data, index_data = None, None
            vertex_ids = vertex_ids_cache
            print(f'Skipped loop data fetching!')

        # Extract requested data from blender vertices
        vertex_data = self.get_vertex_data(mesh, proxy_layout)

        if vertex_data is not None:
            # Output vb is based on actual faces we're going to draw, so we need to make vertex_data match the loop_data
            # Multiple vertices from loop_data may refer the same one from vertex_data
            # Also, some vertices from vertex_data may end up not being required at all (when no faces use them)
            # Luckily, it can be done easily with numpy, and we can use vertex ids from loop_data as index for vertex_data
            vertex_data.set_data(vertex_data.get_data(vertex_ids))

        # Initialize vertex buffer with requested layout
        vertex_buffer = NumpyBuffer(layout, size=len(vertex_ids))

        # Convert received data and import it to output vertex buffer
        if loop_data is not None:
            vertex_buffer.import_data(loop_data, semantic_converters, format_converters)
        if vertex_data is not None:
            vertex_buffer.import_data(vertex_data, semantic_converters, format_converters)
        if index_data is not None:
            for index_converter in semantic_converters.get(AbstractSemantic(Semantic.Index), []):
                index_data = index_converter(index_data)
            for index_converter in format_converters.get(AbstractSemantic(Semantic.Index), []):
                index_data = index_converter(index_data)

        return index_data, vertex_buffer

    def make_proxy_layout(self, 
                          export_layout: BufferLayout,
                          semantic_converters: Dict[AbstractSemantic, List[callable]]) -> BufferLayout:
        # VertexId is required for export process, we should ensure its availability
        proxy_layout = BufferLayout([])
        # Some formats cannot be converted at foreach_get -> numpy request level and require special care
        for export_semantic in export_layout.semantics:
            blender_format = self.blender_data_formats[export_semantic.abstract.enum]
            export_format = export_semantic.format

            proxy_semantic = copy.deepcopy(export_semantic)

            if export_semantic.extract_format is not None:
                # Export format has specified extraction format, lets hope they know what they're doing
                proxy_semantic.format = export_semantic.extract_format
                proxy_semantic.stride = export_semantic.extract_format.byte_width
            elif export_format.dxgi_type in [DXGIType.UNORM16, DXGIType.UNORM8, DXGIType.SNORM16, DXGIType.SNORM8]:
                # Formats UNORM16, UNORM8, SNORM16 and SNORM8 cannot be directly exported and require conversion
                proxy_semantic.format = blender_format
                proxy_semantic.stride = blender_format.byte_width
            elif export_semantic.abstract in semantic_converters.keys():
                # Semantic converter specified and it works with data values
                # Lets extract data in original format to prevent possible precision loss
                if export_semantic.abstract.enum in [Semantic.Blendindices, Semantic.Blendweight]:
                    proxy_semantic.stride = blender_format.byte_width * proxy_semantic.get_num_values()
                    proxy_semantic.format = blender_format
                else:
                    proxy_semantic.format = blender_format
                    proxy_semantic.stride = blender_format.byte_width
            elif export_semantic.abstract.enum not in [Semantic.Blendindices, Semantic.Blendweight]:
                # Only blends can be directly exported with any bitness and padding, because they aren't extracted with foreach_get
                # Other semantics may require conversion:
                if export_format.num_values != blender_format.num_values:
                    # Export formats with different number of values per row and cannot be filled by foreach_get directly
                    proxy_semantic.format = blender_format
                    proxy_semantic.stride = blender_format.byte_width
                elif export_format.value_byte_width > blender_format.value_byte_width:
                    # Export formats with more bits than blender storage and may corrupt data if used directly
                    proxy_semantic.format = blender_format
                    proxy_semantic.stride = blender_format.byte_width
                elif export_semantic.stride != blender_format.value_byte_width:
                    # Export format stride differs from the blender storage and cannot be filled by foreach_get directly
                    proxy_semantic.format = blender_format
                    proxy_semantic.stride = blender_format.byte_width

            proxy_layout.add_element(proxy_semantic)

        return proxy_layout

    def fetch_data(self, 
                   data_source, 
                   data_name: str, 
                   data_type: numpy.dtype, 
                   size: int = 0) -> numpy.ndarray:
        
        if size == 0:
            size = len(data_source)
        result = numpy.empty(size, dtype=data_type)
        data_source.foreach_get(data_name, result.ravel())
        return result

    def get_loop_data(self, 
                      mesh: bpy.types.Mesh, 
                      proxy_layout: BufferLayout, 
                      flip_winding = False, 
                      dedupe = False) -> Tuple[NumpyBuffer, numpy.ndarray]:
        
        start_time = time.time()

        # Make loop data layout
        layout = BufferLayout([])
        for buffer_semantic in proxy_layout.semantics:
            if buffer_semantic.abstract.enum == Semantic.Index:
                continue
            if buffer_semantic.abstract.enum in self.blender_loop_semantics:
                layout.add_element(buffer_semantic)

        # Calculate data for Semantic.Tangent
        mesh.calc_tangents()

        # Initialize loop data storage
        size = len(mesh.loops)
        loop_data = NumpyBuffer(layout, size=size)

        # Fetch data for requested semantics
        for buffer_semantic in proxy_layout.semantics:
            semantic = buffer_semantic.abstract.enum
            semantic_name = buffer_semantic.get_name()
            numpy_type = buffer_semantic.get_numpy_type()
            if semantic == Semantic.VertexId:
                data = self.fetch_data(mesh.loops, 'vertex_index', numpy_type, size)
            elif semantic == Semantic.Normal:
                data = self.fetch_data(mesh.loops, 'normal', numpy_type, size)
            elif semantic == Semantic.Tangent:
                data = self.fetch_data(mesh.loops, 'tangent', numpy_type, size)
            elif semantic == Semantic.BitangentSign:
                data = self.fetch_data(mesh.loops, 'bitangent_sign', numpy_type, size)
            elif semantic == Semantic.Color:
                if hasattr(mesh, 'vertex_colors') and semantic_name in mesh.vertex_colors:
                    # Legacy projects support (for object imported with WWMI Tools 1.3.5 or below)
                    color_attribute = mesh.vertex_colors[semantic_name]
                else:
                    color_attribute = mesh.color_attributes[semantic_name]
                data = self.fetch_data(color_attribute.data, 'color', numpy_type, size)
            elif semantic == Semantic.TexCoord:
                data = self.fetch_data(mesh.uv_layers[semantic_name].data, 'uv', numpy_type, size)
            else:
                continue
            self.sanitize_blender_data(data)
            loop_data.set_field(semantic_name, data)

        # Swap every first with every third vertex for every face aka polygon
        if flip_winding:
            # Create array from 0 to len, it's >10x faster than quering it from Blender via
            # `indices = self.fetch_data(mesh.loops, 'index', (numpy.uint32, 3), int(size/3))`
            # Creates [0, 1, 2, 3, 4, 5] for len=6
            indices = numpy.arange(len(loop_data.data))
            # Convert flat array to 2-dim array of index triads
            # [0, 1, 2, 3, 4, 5] -> [[0, 1, 2], [3, 4, 5]]
            indices = indices.reshape(-1, 3)
            # Swap every first with every third element of index triads
            # [[0, 1, 2], [3, 4, 5]] -> [[2, 1, 0], [5, 4, 3]]
            indices[:, [0, 2]] = indices[:, [2, 0]]
            # Destroy first dimension so we could use the array as index for loop data array
            # [[2, 1, 0], [5, 4, 3]] -> [2, 1, 0, 5, 4, 3]
            indices = indices.flatten()
            # Swap every first with every third element of loop data array
            loop_data.data = loop_data.data[indices]

        # Build IB
        index_data = None
        index_semantic = proxy_layout.get_element(AbstractSemantic(Semantic.Index))
        if index_semantic is not None:
            indexed_vertices = collections.OrderedDict()
            # Note: foreach_get provides loop data in the same order as iteration over polygons
            index_data = [indexed_vertices.setdefault(data.tobytes(), len(indexed_vertices)) for data in loop_data.data]
            index_data = numpy.array(index_data, dtype=index_semantic.get_numpy_type())
                
        # Remove vertices with the exactly same attributes
        if dedupe:
            loop_data.remove_duplicates()

        print(f'Loop data fetch time: {time.time() - start_time :.3f}s ({len(loop_data.get_data())} vertices, {len(index_data)} indices)')

        return loop_data, index_data

    def get_vertex_data(self, 
                        mesh: bpy.types.Mesh, 
                        proxy_layout: BufferLayout) -> NumpyBuffer:
        
        start_time = time.time()

        # Make vertex data layout
        layout = BufferLayout([])
        for buffer_semantic in proxy_layout.semantics:
            if buffer_semantic.abstract.enum in self.blender_vertex_semantics:
                layout.add_element(buffer_semantic)

        if len(layout.semantics) == 0:
            print(f'Skipped vertex data fetching!')
            return None

        # Initialize vertex data storage
        size = len(mesh.vertices)
        vertex_data = NumpyBuffer(layout, size=size)

        vertex_groups = None
        for buffer_semantic in proxy_layout.semantics:
            if buffer_semantic.abstract.enum in [Semantic.Blendindices, Semantic.Blendweight]:
                vertex_groups = [sorted(vertex.groups, key=attrgetter('weight'), reverse=True)
                                 for vertex in mesh.vertices]
                break

        # Fetch data for requested semantics
        for buffer_semantic in proxy_layout.semantics:
            semantic = buffer_semantic.abstract.enum
            numpy_type = buffer_semantic.get_numpy_type()

            if semantic == Semantic.Position:
                data = self.fetch_data(mesh.vertices, 'undeformed_co', numpy_type, size)
            elif semantic == Semantic.Blendindices:
                dtype = numpy_type[0] if isinstance(numpy_type, tuple) else numpy_type
                num_vgs = buffer_semantic.get_num_values()
                data = numpy.array([[vg.group for vg in groups[:num_vgs]] + [0] * (num_vgs - len(groups))
                                    for groups in vertex_groups], dtype=dtype)
            elif semantic == Semantic.Blendweight:
                dtype = numpy_type[0] if isinstance(numpy_type, tuple) else numpy_type
                num_vgs = buffer_semantic.get_num_values()
                data = numpy.array([[vg.weight for vg in groups[:num_vgs]] + [0] * (num_vgs - len(groups))
                                    for groups in vertex_groups], dtype=dtype)
            else:
                continue
            
            self.sanitize_blender_data(data)
            
            vertex_data.set_field(buffer_semantic.get_name(), data)

        print(f'Vertex data fetch time: {time.time() - start_time :.3f}s ({len(vertex_data.get_data())} vertices)')

        return vertex_data

    def get_shapekey_data(self, 
                          obj: bpy.types.Object, 
                          names_filter: Optional[List[str]] = None, 
                          deduct_basis = False) -> Dict[str, numpy.ndarray]:
        
        start_time = time.time()

        numpy_type = self.blender_data_formats[Semantic.ShapeKey].get_numpy_type()

        base_data = None
        if deduct_basis:
            base_data = self.fetch_data(obj.data.shape_keys.key_blocks['Basis'].data, 'co', numpy_type)

        result = {}

        for shapekey in obj.data.shape_keys.key_blocks:
            if names_filter is not None:
                if shapekey.name not in names_filter:
                    continue
            elif deduct_basis and shapekey.name == 'Basis':
                continue

            data = self.fetch_data(shapekey.data, 'co', numpy_type)

            self.sanitize_blender_data(data)

            if deduct_basis:
                data -= base_data

            result[shapekey.name] = data

        print(f'Shape Keys fetch time: {time.time() - start_time :.3f}s ({len(result)} shapekeys)')

        return result

    @staticmethod
    def sanitize_blender_data(arr: numpy.ndarray):
        if numpy.issubdtype(arr.dtype, numpy.floating):
            numpy.nan_to_num(arr, copy=False)
