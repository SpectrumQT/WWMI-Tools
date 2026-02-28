import io
import copy
import textwrap
import math
import numpy
import re

from typing import Union, List, Optional, Dict, Iterable
from dataclasses import dataclass, fields
from enum import Enum
from pathlib import Path
from operator import attrgetter

from .dxgi_format import *


class Topology(Enum):
    Undefined = 'undefined'
    PointList = 'pointlist'
    LineList = 'linelist'
    LineStrip = 'linestrip'
    TriangleList = 'trianglelist'
    TriangleStrip = 'trianglestrip'
    LineListAdj = 'linelist_adj'
    LineStripAdj = 'linestrip_adj'
    TriangleListAdj = 'trianglelist_adj'
    TriangleStripAdj = 'trianglestrip_adj'

    # Patchlists
    ControlPointPatchList1 = '1_control_point_patchlist'
    ControlPointPatchList2 = '2_control_point_patchlist'
    ControlPointPatchList3 = '3_control_point_patchlist'
    ControlPointPatchList4 = '4_control_point_patchlist'
    ControlPointPatchList5 = '5_control_point_patchlist'
    ControlPointPatchList6 = '6_control_point_patchlist'
    ControlPointPatchList7 = '7_control_point_patchlist'
    ControlPointPatchList8 = '8_control_point_patchlist'
    ControlPointPatchList9 = '9_control_point_patchlist'
    ControlPointPatchList10 = '10_control_point_patchlist'
    ControlPointPatchList11 = '11_control_point_patchlist'
    ControlPointPatchList12 = '12_control_point_patchlist'
    ControlPointPatchList13 = '13_control_point_patchlist'
    ControlPointPatchList14 = '14_control_point_patchlist'
    ControlPointPatchList15 = '15_control_point_patchlist'
    ControlPointPatchList16 = '16_control_point_patchlist'
    ControlPointPatchList17 = '17_control_point_patchlist'
    ControlPointPatchList18 = '18_control_point_patchlist'
    ControlPointPatchList19 = '19_control_point_patchlist'
    ControlPointPatchList20 = '20_control_point_patchlist'
    ControlPointPatchList21 = '21_control_point_patchlist'
    ControlPointPatchList22 = '22_control_point_patchlist'
    ControlPointPatchList23 = '23_control_point_patchlist'
    ControlPointPatchList24 = '24_control_point_patchlist'
    ControlPointPatchList25 = '25_control_point_patchlist'
    ControlPointPatchList26 = '26_control_point_patchlist'
    ControlPointPatchList27 = '27_control_point_patchlist'
    ControlPointPatchList28 = '28_control_point_patchlist'
    ControlPointPatchList29 = '29_control_point_patchlist'
    ControlPointPatchList30 = '30_control_point_patchlist'
    ControlPointPatchList31 = '31_control_point_patchlist'
    ControlPointPatchList32 = '32_control_point_patchlist'

    def __str__(self):
        return f'{self.value}'

    def __repr__(self):
        return f'{self.value}'


SEMANTIC_ALIASES = {
    'BLENDWEIGHT': 'BLENDWEIGHTS',
}

class Semantic(Enum):
    VertexId = 'VERTEXID'
    Index = 'INDEX'
    Tangent = 'TANGENT'
    BitangentSign = 'BITANGENTSIGN'
    Normal = 'NORMAL'
    TexCoord = 'TEXCOORD'
    Color = 'COLOR'
    Position = 'POSITION'
    Blendindices = 'BLENDINDICES'
    Blendweight = 'BLENDWEIGHT'
    Blendweights = 'BLENDWEIGHTS'
    ShapeKey = 'SHAPEKEY'
    RawData = 'RAWDATA'
    EncodedData = 'ENCODEDDATA'
    Attribute = 'ATTRIBUTE'

    def __str__(self):
        return f'{self.value}'

    def __repr__(self):
        return f'{self.value}'

    def __eq__(self, other):
        if isinstance(other, str):
            return self.value == other or SEMANTIC_ALIASES.get(self.value) == other
        if isinstance(other, Semantic):
            return self.value == other.value or SEMANTIC_ALIASES.get(self.value) == other.value
        return super().__eq__(other)

    def __hash__(self):
        return hash(self.value)


class InputSlotClass(Enum):
    PerVertex = 'per-vertex'
    PerInstance = 'per-instance'

    def __str__(self):
        return f'{self.value}'

    def __repr__(self):
        return f'{self.value}'


@dataclass
class AbstractSemantic:
    enum: Semantic
    index: int = 0

    def __init__(self, semantic, semantic_index=0):
        self.enum = semantic
        self.index = semantic_index

    def __hash__(self):
        return hash((self.enum, self.index))

    def __str__(self):
        return f'{self.enum}_{self.index}'

    def __repr__(self):
        return f'{self.enum}_{self.index}'
    
    def get_name(self):
        name = self.enum.value
        if self.index > 0:
            name += str(self.index)
        if self.enum == Semantic.TexCoord:
            name += '.xy'
        return name


@dataclass
class BufferSemantic:
    abstract: AbstractSemantic
    format: DXGIFormat
    stride: int = 0
    offset: int = 0
    name: Optional[str] = None
    input_slot: int = 0
    input_slot_class: InputSlotClass = InputSlotClass.PerVertex
    instance_data_step_rate: int = 0
    import_format: Optional[DXGIFormat] = None
    extract_format: Optional[DXGIFormat] = None

    def __post_init__(self):
        # Calculate byte stride
        if self.stride == 0:
            self.stride = self.format.byte_width
        
    def __hash__(self):
        return hash((self.abstract, self.input_slot, self.format.format, self.stride, self.offset))

    def __repr__(self):
        return f'{self.abstract} ({self.format.format} input={self.input_slot} stride={self.stride} offset={self.offset})'

    def to_string(self, indent=2):
        return textwrap.indent(textwrap.dedent(f'''
            SemanticName: {self.abstract.enum}
            SemanticIndex: {self.abstract.index}
            Format: {self.format.format}
            InputSlot: {self.input_slot}
            AlignedByteOffset: {self.offset}
            InputSlotClass: {self.input_slot_class}
            InstanceDataStepRate: 0
        ''').lstrip(), ' ' * indent)

    def get_format(self) -> str:
        return self.format.get_format()

    def get_name(self) -> str:
        return self.name if self.name else self.abstract.get_name()

    def get_num_values(self) -> int:
        return self.format.get_num_values(self.stride)

    def get_numpy_type(self) -> Union[int, Tuple[Union[numpy.integer, numpy.floating], int]]:
        return self.format.get_numpy_type(self.stride)
    

@dataclass
class BufferLayout:
    semantics: List[BufferSemantic]
    stride: int = 0
    force_stride: bool = False
    auto_stride: bool = True
    auto_offsets: bool = True

    def __post_init__(self):
        # Autofill byte Stride and Offsets
        if self.auto_stride and self.stride == 0:
            self.fill_stride()
            if self.auto_offsets:
                self.fill_offsets()
        # Autofill Semantic Index
        groups = {}
        for semantic in self.semantics:
            if semantic not in groups:
                groups[semantic] = 0
                continue
            if semantic.abstract.index == 0:
                groups[semantic] += 1
                semantic.abstract.index = groups[semantic]

    def fill_stride(self):
        self.stride = self.calculate_stride()

    def calculate_stride(self):
        stride = 0
        for element in self.semantics:
            stride += element.stride
        return stride

    def fill_offsets(self):
        offset = 0
        for element in self.semantics:
            element.offset = offset
            offset += element.stride

    def get_element(self, element: Union[AbstractSemantic, Semantic, int]) -> Optional[BufferSemantic]:
        
        if isinstance(element, str):
            for layout_element in self.semantics:
                if element == layout_element.get_name():
                    return layout_element
            # raise ValueError(f'Layout element with name {element} is not found!')
            return None

        if isinstance(element, int):
            if element >= len(self.semantics):
                # raise ValueError(f'Layout element with id {element} is out of 0-{len(self.semantics)} bounds!')
                return None
            return self.semantics[element]
        
        if isinstance(element, Semantic):
            element = AbstractSemantic(element)

        if not isinstance(element, AbstractSemantic):
            raise ValueError(f'Layout element search by type {type(element)} of value {element} is not supported!')
        
        for layout_element in self.semantics:
            if element == layout_element.abstract:
                return layout_element
            
        return None

    def set_element(self, abstract: AbstractSemantic, semantic: BufferSemantic):
        for i, element in enumerate(self.semantics):
            if abstract == element.abstract:
                self.stride -= element.stride
                self.semantics[i] = semantic
                self.stride += semantic.stride
                if self.auto_stride:
                    self.fill_stride()
                    if self.auto_offsets:
                        self.fill_offsets()
                return
        raise ValueError(f'Buffer semantic {abstract} not found in layout!')

    def add_element(self, semantic: BufferSemantic):
        if self.get_element(semantic.abstract) is not None:
            return
        semantic = copy.deepcopy(semantic)
        if self.auto_offsets:
            semantic.offset = self.stride
        if self.auto_stride:
            self.stride += semantic.stride
        self.semantics.append(semantic)

    def merge(self, layout: 'BufferLayout'):
        for semantic in layout.semantics:
            if not self.get_element(semantic.abstract):
                self.add_element(semantic)

    def to_string(self):
        ret = ''
        for i, semantic in enumerate(self.semantics):
            ret += 'element[%i]:\n' % i
            ret += semantic.to_string()
        return ret

    def get_numpy_type(self):
        dtype = numpy.dtype([])
        for semantic in self.semantics:
            dtype = numpy.dtype(dtype.descr + [(semantic.abstract.get_name(), (semantic.get_numpy_type()))])
        return dtype
    
    def get_max_input_slot(self) -> int:
        return max([semantic.input_slot for semantic in self.semantics])
    
    def get_elements_in_slot(self, input_slot: int) -> List[BufferSemantic]:
        return [semantic for semantic in self.semantics if semantic.input_slot == input_slot]
    
    def sort(self):
        self.semantics.sort(key=attrgetter('input_slot', 'offset'))
    
    def remove_data_views(self):
        filtered_semantics = []
        for input_slot in range(self.get_max_input_slot()+1):
            semantics = self.get_elements_in_slot(input_slot)
            offset = 0
            slot_semantics = []
            # prev_semantic = None
            for semantic in semantics:
                if semantic.offset < offset:
                    # if prev_semantic and semantic.stride != prev_semantic.stride:
                    #     raise ValueError(f'unexpected data view {semantic.abstract} stride {semantic.stride} (expected {prev_semantic.stride}) for semantic {semantic}')
                    continue
                slot_semantics.append(semantic)
                # prev_semantic = semantic
                offset += semantic.stride
            filtered_semantics += slot_semantics
        self.semantics = filtered_semantics


class NumpyBuffer:
    layout: BufferLayout
    data: numpy.ndarray

    def __init__(self, layout: BufferLayout, data: Optional[numpy.ndarray] = None, size = 0):
        self.set_layout(layout)
        self.set_data(data, size)

    def set_layout(self, layout: BufferLayout):
        self.layout = layout

    def set_data(self, data: Optional[numpy.ndarray], size = 0):
        if data is not None:
            self.data = data
        elif size > 0:
            self.data = numpy.zeros(size, dtype=self.layout.get_numpy_type())

    def set_field(self, field: Union[AbstractSemantic, Semantic, int, str], data: Optional[numpy.ndarray]):
        semantic = self.layout.get_element(field)
        if semantic is None:
            raise ValueError(f'Semantic {field} not found in the layout of NumpyBuffer!')
        try:
            self.data[semantic.get_name()] = data
        except Exception as e:
            raise ValueError(f'Failed to set field {field} data for semantic {semantic}: {str(e)}') from e

    def get_data(self, indices: Optional[numpy.ndarray] = None) -> numpy.ndarray:
        if indices is None:
            return self.data
        else:
            return self.data[indices]

    def get_field(self, field: Union[AbstractSemantic, Semantic, int, str]) -> Optional[numpy.ndarray]:
        semantic = self.layout.get_element(field)
        if semantic is None:
            # raise ValueError(f'Semantic {field} not found in the layout of NumpyBuffer!')
            return None
        return self.data[semantic.get_name()]

    def remove_duplicates(self, keep_order = True):
        if keep_order:
            _, unique_index = numpy.unique(self.data, return_index=True)
            self.data = self.data[numpy.sort(unique_index)]
        else:
            self.data = numpy.unique(self.data)

    def import_semantic_data(self,
                             data: numpy.ndarray, 
                             semantic: Union[BufferSemantic, int], 
                             semantic_converters: Optional[List[callable]] = None,
                             format_converters: Optional[List[callable]] = None):
        
        if isinstance(semantic, int):
            semantic = self.layout.semantics[semantic]
        current_semantic = self.layout.get_element(semantic.abstract)
        if current_semantic is None:
            raise ValueError(f'NumpyBuffer is missing {semantic.abstract} semantic data!')
        if semantic_converters is not None:
            for data_converter in semantic_converters:
                data = data_converter(data)
        if format_converters is not None:
            for data_converter in format_converters:
                data = data_converter(data)
        if data.dtype != current_semantic.format.numpy_base_type:
            data = current_semantic.format.type_encoder(data)
        try:
            self.set_field(current_semantic.get_name(), data)
        except Exception as e:
            raise ValueError(f'Failed to import semantic {semantic} to buffer layout {self.layout}: {str(e)}') from e
        
    def import_data(self,
                    data: 'NumpyBuffer',
                    semantic_converters: Dict[AbstractSemantic, List[callable]],
                    format_converters: Dict[AbstractSemantic, List[callable]]):
        
        for buffer_semantic in self.layout.semantics:

            data_semantic = data.layout.get_element(buffer_semantic.abstract)

            if data_semantic is None:
                continue
            field_data = data.get_field(buffer_semantic.get_name())

            self.import_semantic_data(
                field_data, 
                data_semantic,
                semantic_converters.get(buffer_semantic.abstract, []),
                format_converters.get(buffer_semantic.abstract, []))
            
    def import_raw_data(self, data: numpy.ndarray):
        self.data = numpy.frombuffer(data, dtype=self.layout.get_numpy_type())

    def import_txt_data(self, data: str, remapped_semantics):
        remapped_semantics = remapped_semantics or {}
        # Build regex pattern dynamically
        pattern_lines = []

        # float_pattern = r"[+-]?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?"
        float_pattern = r"[+-]?(?:\d+(?:\.\d*)?(?:[eE][+-]?\d+)?|nan)"

        # Strict matching
        # for i, semantic in enumerate(self.layout.semantics):
        #     semantic_name = remapped_semantics.get(semantic.abstract, semantic).get_name()
        #     semantic_name = semantic_name.split('.')[0]
        #     # Each number in its own capture group
        #     groups = ",".join([f"({float_pattern})" for _ in range(semantic.get_num_values())])
        #     groups = groups.replace(",", r",\s*")
        #     newline = r"\s*\n" if i < len(self.layout.semantics) - 1 else ""
        #     # Match optional prefix "vb0[...]"
        #     line_pattern = rf"vb0\[\d+\]\+\d+\s+{semantic_name}:\s*{groups}{newline}"
        #     pattern_lines.append(line_pattern)

        for semantic in self.layout.semantics:
            semantic_name = remapped_semantics.get(semantic.abstract, semantic).get_name()
            semantic_name = semantic_name.split('.')[0]
            groups = ",".join([f"({float_pattern})" for _ in range(semantic.get_num_values())])
            groups = groups.replace(",", r",\s*")
            line_pattern = rf"vb\d+\[\d+\]\+\d+\s+{semantic_name}:\s*{groups}\s*\n?"
            pattern_lines.append(line_pattern)
            
        # Join all lines
        full_pattern = "".join(pattern_lines)

        # Compile regex
        pattern = re.compile(full_pattern)

        matches = pattern.findall(data)
        if not matches:
            raise ValueError
        
        data = numpy.array(matches, dtype=numpy.float32)  # parse floats first

        # Fill fields
        start = 0
        for semantic in self.layout.semantics:
            n = semantic.get_num_values()
            field_data = data[:, start:start+n].astype(semantic.format.numpy_base_type)
            if n == 1:
                field_data = field_data.ravel()
            self.set_field(semantic.get_name(), field_data)
            start += n

    def get_bytes(self):
        return self.data.tobytes()

    def __len__(self):
        return len(self.data)


MIGOTO_FORMAT_HEADER_CONVERTERS = {
    'topology': lambda value: Topology(value),
    'format': lambda value: DXGIFormat(value.replace('DXGI_FORMAT_', '')),
}


MIGOTO_FORMAT_ELEMENT_CONVERTERS = {
    'SemanticName': lambda value: Semantic(value),
    'Format': lambda value: DXGIFormat(value.replace('DXGI_FORMAT_', '')),
    'InputSlotClass': lambda value: InputSlotClass(value),
}


@dataclass
class MigotoFormat:
    # Common
    byte_offset: int = 0
    topology: Optional[Topology] = None
    # IB
    format: Optional[DXGIFormat] = None
    first_index: int = 0
    index_count: int = 0
    # VB
    stride: int = 0
    first_vertex: int = 0
    vertex_count: int = 0
    first_instance: int = 0
    instance_count: int = 0
    # Semantics
    ib_layout: Optional[BufferLayout] = None
    vb_layout: Optional[BufferLayout] = None

    def __post_init__(self):
        self.verify_migoto_format()

    @classmethod
    def from_paths(
        cls,
        fmt_path: Optional[Path] = None, 
        vb_path: Optional[Path] = None,
        ib_path: Optional[Path] = None,
    ) -> 'MigotoFormat':
        
        # Try to auto-detect fmt path from VB path
        if fmt_path is None and vb_path and vb_path.is_file():
            fmt_path = vb_path.with_suffix('.fmt')

        # Try to auto-detect fmt path from IB path
        if fmt_path is None and ib_path and ib_path.is_file():
            fmt_path = ib_path.with_suffix('.fmt')

        # Raise exceptions if fmt file resolution failed
        if fmt_path is None:
            raise ValueError(f'Failed to resolve format file for VB `{vb_path}` and IB `{ib_path}`')
        if not fmt_path.is_file():
            raise FileNotFoundError(f'Format file does not exist: {fmt_path}')

        # Read migoto format from fmt file
        with open(fmt_path, 'r') as fmt_file:
            fmt = MigotoFormat.from_fmt_file(fmt_file)     

        return fmt
    
    @classmethod
    def from_dict(cls, migoto_data: dict) -> 'MigotoFormat':
        # Tokenize header data
        tokenized_headers_data = cls.tokenize_data(migoto_data, MIGOTO_FORMAT_HEADER_CONVERTERS)

        # Initialize instance with header data
        fmt = cls(**{
            f.name: tokenized_headers_data[f.name]
            for f in fields(cls)
            if f.name in tokenized_headers_data
        })

        # Fill IB layout ("format" field always carries INDEX0 one)
        if fmt.format is not None:
            # Initialzie IB and add INDEX0 semantic
            fmt.ib_layout = BufferLayout(semantics=[], auto_stride=True, auto_offsets=False)
            index_semantic = BufferSemantic(AbstractSemantic(Semantic.Index, 0), format=fmt.format)
            # Auto-fix semantic stride for common topoligies
            # 3dmigoto writes only R component here (i.e. R16_UINT with for R16G16B16_UINT)
            if fmt.topology == Topology.TriangleList:
                index_semantic.stride = 3 * index_semantic.format.value_byte_width
            elif fmt.topology == Topology.LineList:
                index_semantic.stride = 2 * index_semantic.format.value_byte_width
            # Add INDEX0 to IB
            fmt.ib_layout.add_element(index_semantic)

        # Get layout data and exit early if not found
        elements_data = migoto_data.get('elements', None)
        if elements_data is None:
            return fmt

        # Tokenize elements data
        tokenized_elements_data = {}
        for element_id, element_data in migoto_data['elements'].items():
            tokenized_elements_data[element_id] = cls.tokenize_data(element_data, MIGOTO_FORMAT_ELEMENT_CONVERTERS)

        # Fill instance with elements data

        layout = BufferLayout(semantics=[], auto_stride=False, auto_offsets=False)

        for element in tokenized_elements_data.values():
            buffer_semantic = BufferSemantic(
                abstract=AbstractSemantic(
                    semantic=element['SemanticName'],
                    semantic_index=element['SemanticIndex'],
                ),
                format=element['Format'],
                input_slot=element['InputSlot'],
                offset=element['AlignedByteOffset'],
                input_slot_class=element['InputSlotClass'],
                instance_data_step_rate=element['InstanceDataStepRate'],
            )
            
            layout.add_element(buffer_semantic)

        fmt.vb_layout = layout

        return fmt
    
    @classmethod
    def parse_fmt_text(cls, lines: str) -> dict:
        migoto_data = {}
        elements_data = {}
        current_element = None

        for line in lines.splitlines():
            line: str = line.lstrip()

            if not line:
                continue

            if ':' not in line:
                # raise ValueError(f'separator `:` not found in `{line}`')
                break

            if line.startswith('element['):
                end = line.find(']')
                if end == -1:
                    raise ValueError(f'element line is corrupted (missing `]`): `{line}`')
                start = len('element[')
                element_id = int(line[start:end].strip())
                current_element = {}
                elements_data[element_id] = current_element
                continue

            k, v = map(str.strip, line.split(':', 1))

            if current_element is not None:
                current_element[k] = v
            else:
                migoto_data[k.replace(' ', '_')] = v

        migoto_data['elements'] = elements_data

        return migoto_data
    
    @classmethod
    def from_fmt_text(cls, text: str) -> 'MigotoFormat':
        migoto_data = cls.parse_fmt_text(text)
        return cls.from_dict(migoto_data)
    
    @classmethod
    def from_fmt_file(cls, file_data: io.IOBase) -> 'MigotoFormat':
        migoto_data = cls.parse_fmt_text(file_data.read())
        return cls.from_dict(migoto_data)

    @classmethod
    def extract_txt_file_fmt_text(cls, file_data: io.IOBase) -> dict:
        lines = ''
        for line in file_data:
            if not line.strip():
                continue
            if ':' not in line:
                break
            if line.startswith(('vertex-data', 'instance-data')):
                break
            lines += line
        return lines
    
    @classmethod
    def from_txt_file(cls, file_data: io.IOBase) -> 'MigotoFormat':
        fmt_text = cls.extract_txt_file_fmt_text(file_data)
        migoto_data = cls.parse_fmt_text(fmt_text)
        return cls.from_dict(migoto_data)

    @staticmethod
    def tokenize_data(element_data: Dict[str, str], converters: Dict[str, callable]) -> dict:
        tokenized_data = {}
        for k, v in element_data.items():
            converter = converters.get(k, None)
            if converter:
                tokenized_data[k] = converter(v)
            elif isinstance(v, str):
                tokenized_data[k] = int(v)
        return tokenized_data

    def verify_migoto_format(self):
        pass

    @classmethod
    def from_layouts(cls, vb_layout: Optional[BufferLayout] = None, ib_layout: Optional[BufferLayout] = None) -> 'MigotoFormat':
        fmt = cls(
            ib_layout=ib_layout,
            vb_layout=vb_layout,
        )
        return fmt


class MigotoFmt:
    def __init__(self, fmt_file: io.IOBase):
        """
        DEPRECATED!!! Use MigotoFormat instead!
        This class approach is based on assumption that all elements declare single continuos buffer
        While it's valid for native toolkit FMTs, it falls short when it comes to TXT headers parsing
        """
        fmt = MigotoFormat.from_fmt_file(fmt_file)

        # Relay layouts
        self.ib_layout = fmt.ib_layout
        self.vb_layout = fmt.vb_layout
        
        # Calculate per-element stride
        vb_stride = 0
        vb_byte_offset = 0
        for i, element in enumerate(fmt.vb_layout.semantics):
            next_element_id = i + 1
            if len(fmt.vb_layout.semantics) > next_element_id:
                next_offset = fmt.vb_layout.semantics[next_element_id].offset
            else:
                next_offset = vb_stride
            element.stride = next_offset - vb_byte_offset
            vb_byte_offset = next_offset

        if vb_stride != self.vb_layout.stride:
            raise ValueError(f'vb buffer layout format stride mismatch: {vb_stride} != {self.vb_layout.stride}')



        

class BufferElement:
    def __init__(self, buffer, index):
        self.buffer = buffer
        self.index = index
        self.layout = self.buffer.layout

    def get_bytes(self, semantic, return_buffer_semantic=False):
        if isinstance(semantic, AbstractSemantic):
            semantic = self.layout.get_element(semantic)
        byte_offset = self.index * semantic.stride
        data_bytes = self.buffer.data[semantic][byte_offset : byte_offset + semantic.stride]
        if not return_buffer_semantic:
            return data_bytes
        else:
            return data_bytes, semantic

    def set_bytes(self, semantic, data_bytes):
        if isinstance(semantic, AbstractSemantic):
            semantic = self.layout.get_element(semantic)
        byte_offset = self.index * semantic.stride
        self.buffer.data[semantic][byte_offset: byte_offset + semantic.stride] = data_bytes

    def get_value(self, semantic):
        if isinstance(semantic, AbstractSemantic):
            semantic = self.layout.get_element(semantic)
        data_bytes = self.get_bytes(semantic)
        return semantic.format.decoder(data_bytes).tolist()

    def set_value(self, semantic, value):
        if isinstance(semantic, AbstractSemantic):
            semantic = self.layout.get_element(semantic)
        self.set_bytes(semantic, semantic.format.encoder(value).tobytes())

    def get_all_bytes(self):
        data_bytes = bytearray()
        for semantic in self.layout.semantics:
            data_bytes.extend(self.get_bytes(semantic))
        return data_bytes


class ByteBuffer:
    def __init__(self, layout, data_bytes=None):
        self.layout = None
        self.data = {}
        self.num_elements = 0

        self.update_layout(layout)

        if data_bytes is not None:
            self.from_bytes(data_bytes)

    def validate(self):
        result = {}
        for semantic in self.layout.semantics:
            result[semantic] = len(self.data[semantic]) / semantic.stride
        if min(result.values()) != max(result.values()):
            result = ', '.join([f'{k.abstract}: {v}' for k, v in result.items()])
            raise ValueError(f'elements count mismatch in buffers: {result}')
        if len(self.layout.semantics) != len(self.data):
            raise ValueError(f'data structure must match buffer layout!')
        self.num_elements = int(min(result.values()))

    def update_layout(self, layout):
        self.layout = layout
        if len(self.data) != 0:
            self.validate()

    def from_bytes(self, data_bytes):
        if self.layout.force_stride:
            data_bytes.extend(bytearray((math.ceil(len(data_bytes) / self.layout.stride)) * self.layout.stride - len(data_bytes)))

        num_elements = len(data_bytes) / self.layout.stride
        if num_elements % 1 != 0:
            raise ValueError(f'buffer stride {self.layout.stride} must be multiplier of bytes len {len(data_bytes)}')
        num_elements = int(num_elements)

        self.data = {}
        for semantic in self.layout.semantics:
            self.data[semantic] = bytearray()

        byte_offset = 0
        for element_id in range(num_elements):
            for semantic in self.layout.semantics:
                self.data[semantic].extend(data_bytes[byte_offset:byte_offset+semantic.stride])
                byte_offset += semantic.stride

        if byte_offset != len(data_bytes):
            raise ValueError(f'layout mismatch: input ended at {byte_offset} instead of {len(data_bytes)}')

        self.validate()

    def get_element(self, index):
        return BufferElement(self, index)

    def extend(self, num_elements):
        if num_elements <= 0:
            raise ValueError(f'cannot extend buffer by {num_elements} elements')
        for semantic in self.layout.semantics:
            if semantic in self.data:
                self.data[semantic].extend(bytearray(num_elements * semantic.stride))
            else:
                self.data[semantic] = bytearray(num_elements * semantic.stride)
        self.validate()

    def get_fragment(self, offset, element_count):
        fragment = ByteBuffer(self.layout)
        for semantic in self.layout.semantics:
            byte_offset = offset * semantic.stride
            byte_count = element_count * semantic.stride
            fragment.data[semantic] = self.data[semantic][byte_offset:byte_offset+byte_count]
        fragment.validate()
        return fragment

    def import_buffer(self, src_byte_buffer, semantic_map=None, skip_missing=False):
        """
        Imports elements from source buffer based on their semantics
        Without 'semantic_map' provided creates new 'semantic_map' containing all source semantics
        Errors if any of 'semantic_map' elements is not found in src or dst buffers and 'skip_missing' is False
        """
        # Ensure equal number of elements in both buffers
        if src_byte_buffer.num_elements != self.num_elements:
            raise ValueError('source buffer len %d differs from destination buffer len %d' % (
                    src_byte_buffer.num_elements, self.num_elements))
        
        # Calculate semantic map
        semantic_map = self.map_semantics(src_byte_buffer, self, semantic_map=semantic_map, skip_missing=skip_missing)

        # Import data bytes
        for src_semantic, dst_semantic in semantic_map.items():
            if src_semantic.format == dst_semantic.format:
                self.data[dst_semantic] = src_byte_buffer.data[src_semantic]
            else:
                src_values = src_semantic.format.decoder(src_byte_buffer.data[src_semantic]).tolist()
                self.data[dst_semantic] = dst_semantic.format.encoder(src_values).tobytes()

        self.validate()

    def get_bytes(self, semantic=None):
        if semantic is None:
            data_bytes = bytearray()
            for element_id in range(self.num_elements):
                data_bytes.extend(self.get_element(element_id).get_all_bytes())
            return data_bytes
        else:
            if isinstance(semantic, AbstractSemantic):
                semantic = self.layout.get_element(semantic)
            return self.data[semantic]

    def get_values(self, semantic):
        if isinstance(semantic, AbstractSemantic):
            semantic = self.layout.get_element(semantic)
        data_bytes = self.get_bytes(semantic)
        return semantic.format.decoder(data_bytes).tolist()

    def set_bytes(self, semantic, data_bytes):
        if isinstance(semantic, AbstractSemantic):
            semantic = self.layout.get_element(semantic)
        self.data[semantic] = data_bytes
        self.validate()

    def set_values(self, semantic, values):
        if isinstance(semantic, AbstractSemantic):
            semantic = self.layout.get_element(semantic)
        self.set_bytes(semantic, semantic.format.encoder(values).tobytes())

    @staticmethod
    def map_semantics(src_byte_buffer, dst_byte_buffer, semantic_map=None, skip_missing=False):
        """
        
        """
        verified_semantic_map = {}
        if semantic_map is not None:
            # Semantic map may consist of AbstractSemantic instead of BufferSemantic, we need to convert it in this case
            # AbstractSemantic is independent of buffer specifics and contains only SemanticName and SemanticIndex
            # BufferSemantic wraps AbstractSemantic and describes where AbstractSemantic is located in given buffer
            for src_semantic, dst_semantic in semantic_map.items():
                # Ensure source semantic location in source buffer
                src_semantic = src_semantic
                if isinstance(src_semantic, AbstractSemantic):
                    src_semantic = src_byte_buffer.layout.get_element(src_semantic)
                if src_semantic not in src_byte_buffer.layout.semantics:
                    if not skip_missing:
                        raise ValueError(f'source buffer has no {src_semantic.abstract} semantic')
                    continue
                # Ensure destination semantic location in destination buffer
                dst_semantic = src_semantic
                if isinstance(src_semantic, AbstractSemantic):
                    dst_semantic = dst_byte_buffer.layout.get_element(dst_semantic)
                if dst_semantic not in dst_byte_buffer.layout.semantics:
                    if not skip_missing:
                        raise ValueError(f'destination buffer has no {dst_semantic.abstract} semantic')
                    continue
                # Add semantic to verified map
                verified_semantic_map[src_semantic] = dst_semantic
        else:
            # If there is no semantics map provided, map everything by default
            for src_semantic in src_byte_buffer.layout.semantics:
                # Locate matching semantic in destination buffer
                dst_semantic = dst_byte_buffer.layout.get_element(src_semantic.abstract)
                if dst_semantic is None:
                    if not skip_missing:
                        raise ValueError(f'destination buffer has no {src_semantic.abstract} semantic')
                    continue
                verified_semantic_map[src_semantic] = dst_semantic

        return verified_semantic_map


class IndexBuffer(ByteBuffer):
    def __init__(self, layout, data, load_indices=True):
        self.offset = None
        self.first_index = None
        self.index_count = None
        self.topology = None
        self.format = None
        self.faces = None

        if isinstance(data, io.IOBase):
            self.parse_format(data)
            if load_indices:
                self.parse_faces(data)
            super().__init__(layout)
        elif isinstance(data, bytearray):
            super().__init__(layout, data)
            self.bytes_to_faces()
        else:
            raise ValueError(f'unknown IB data format {data}')

    def parse_format(self, f):
        for line in map(str.strip, f):
            if line.startswith('byte offset:'):
                self.offset = int(line[13:])
            elif line.startswith('first index:'):
                self.first_index = int(line[13:])
            elif line.startswith('index count:'):
                self.index_count = int(line[13:])
            elif line.startswith('topology:'):
                self.topology = line[10:]
                if line != 'topology: trianglelist':
                    raise ValueError('"%s" is not yet supported' % line)
            elif line.startswith('format:'):
                dxgi_format = line[8:].replace('DXGI_FORMAT_', '')
                self.format = dxgi_format
            elif line == '':
                if any(x is None for x in [self.offset, self.topology, self.format]):
                    raise ValueError('failed to parse IB format')
                break

    def parse_faces(self, f):
        self.faces = []
        for line in map(str.strip, f):
            face = tuple(map(int, line.split()))
            assert (len(face) == 3)
            self.faces.append(face)
        if self.index_count:
            assert (len(self.faces) * 3 == self.index_count)
        else:
            self.index_count = len(self.faces) * 3

    def faces_to_bytes(self):
        indices = []
        for face in self.faces:
            assert (len(face) == 3)
            indices.extend(list(face))
        assert (len(indices) == self.index_count)
        data_bytes = self.layout.semantics[0].format.encoder(indices).tobytes()
        self.from_bytes(data_bytes)
        assert (self.num_elements * 3 == self.index_count)

    def bytes_to_faces(self):
        self.faces = []
        for element_id in range(self.num_elements):
            face = self.get_element(element_id).get_value(self.layout.semantics[0])
            self.faces.append(tuple(face))

    def get_bytes(self, semantic=None):
        if self.num_elements * 3 != self.index_count:
            self.faces_to_bytes()
        assert (self.num_elements * 3 == self.index_count)
        return super().get_bytes(semantic)
    
    def get_numpy_array(self):
        return numpy.frombuffer(self.get_bytes(), dtype=self.layout.semantics[0].get_numpy_type())

    def get_format(self):
        return self.layout.get_element(AbstractSemantic(Semantic.Index)).get_format()