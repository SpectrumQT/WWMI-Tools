
import os
import shutil
import hashlib
import re

from enum import Enum, auto

from .dict_filter import DictFilter, FilterCondition, Filter


class ShaderType(Enum):
    Empty = 'null'
    Compute = 'cs'
    Pixel = 'ps'
    Vertex = 'vs'
    Geometry = 'gs'
    Hull = 'hs'
    Domain = 'ds'


class BufferType(Enum):
    Blend = auto()
    Normal = auto()
    Position = auto()
    TexCoord = auto()
    ShapeKeyGroup = auto()
    ShapeKeyVertId = auto()
    ShapeKeyColor = auto()


class SlotType(Enum):
    ConstantBuffer = 'cb'
    IndexBuffer = 'ib'
    VertexBuffer = 'vb'
    Texture = 't'
    RenderTarget = 'o'
    UAV = 'u'


def SlotId(slot_id):
    return int(slot_id)


shader_type_codepage = {
    'cs': ShaderType.Compute,
    'ps': ShaderType.Pixel,
    'vs': ShaderType.Vertex,
    'gs': ShaderType.Geometry,
    'hs': ShaderType.Hull,
    'ds': ShaderType.Domain,
}

slot_type_codepage = {
    'o': SlotType.RenderTarget,
    't': SlotType.Texture,
    'u': SlotType.UAV,
    'cb': SlotType.ConstantBuffer,
    'ib': SlotType.IndexBuffer,
    'vb': SlotType.VertexBuffer,
}


class ShaderRef:
    def __init__(self, raw_shader_ref):
        self.raw = raw_shader_ref
        self.type = None
        self.hash = None
        self.parse_raw_ref()
        self.validate()

    def validate(self):
        if self.type is None:
            raise ValueError(f'Failed to parse shader ref "{self.raw}": shader type not detected!')
        if self.hash is None:
            raise ValueError(f'Failed to parse shader ref "{self.raw}": shader hash not detected!')

    def parse_raw_ref(self):
        result = self.raw.split('=')
        if len(result) != 2:
            return
        self.parse_raw_shader_ref(result[0])
        self.hash = result[1]

    def parse_raw_shader_ref(self, raw_shader_ref):
        self.type = shader_type_codepage.get(raw_shader_ref, None)


class ResourceData:
    def __init__(self, file_path):
        self.path = file_path
        self.bytes = None
        self.len = None
        self.sha256 = None

    def load(self):
        with open(self.path, "rb") as f:
            self.bytes = bytearray(f.read())

    def unload(self):
        self.bytes = None

    def update_hash(self):
        if self.bytes is None:
            raise ValueError("Failed to update resource hash: file not loaded!")
        self.sha256 = hashlib.sha256(self.bytes).hexdigest()

    def update_len(self):
        if self.bytes is None:
            raise ValueError("Failed to update resource data len: file not loaded!")
        self.len = len(self.bytes)


class ResourceDescriptor:
    def __init__(self, resource_file_path, calculate_sha256=False):
        self.path = resource_file_path
        self.raw = os.path.basename(resource_file_path)
        self.marked = False
        self.call = None
        self.call_id = None
        self.ext = None
        self.slot_type = None
        self.slot_id = None
        self.slot_shader_type = None
        self.hash = None
        self.old_hash = None
        self.dhash = None
        self.format = None
        self.data = ResourceData(self.path)
        self.shaders = []
        if calculate_sha256:
            self.hash_data()
        self.parse_raw_call()
        self.validate()

    def __repr__(self):
        return self.raw

    def validate(self):
        if self.call_id is None:
            raise ValueError(f'Failed to parse raw descriptor "{self.raw}": no call id detected!')
        if self.slot_type is None:
            raise ValueError(f'Failed to parse raw descriptor "{self.raw}": slot type not detected!')
        if len(self.shaders) == 0:
            raise ValueError(f'Failed to parse raw descriptor "{self.raw}": no shader refs detected!')

    def get_sha256(self):
        is_unloaded = self.data.sha256 is None
        if is_unloaded:
            self.data.load()
            self.data.update_hash()
            self.data.update_len()
        sha256 = self.data.sha256
        if is_unloaded:
            self.data.unload()
        return sha256

    def get_len(self):
        is_unloaded = self.data.len is None
        if is_unloaded:
            self.data.load()
            self.data.update_hash()
            self.data.update_len()
        data_len = self.data.len
        if is_unloaded:
            self.data.unload()
        return data_len

    def hash_data(self):
        self.data.load()
        self.data.update_hash()
        self.data.update_len()
        self.data.unload()

    def get_bytes(self):
        is_unloaded = self.data.bytes is None
        if is_unloaded:
            self.data.load()
        data_bytes = self.data.bytes
        if is_unloaded:
            self.data.unload()
        return data_bytes
    
    def get_slot(self):
        return f'{self.slot_shader_type.value}-{self.slot_type.value}{self.slot_id}'
    
    def get_slot_hash(self):
        return f'{self.get_slot()}-{self.hash}'

    def parse_raw_call(self):
        raw_call = self.raw
        # Process '!U!' mark
        if raw_call.find('!U!') != -1:
            self.marked = True
            raw_call = raw_call.replace('!U!=', '')
        # Match call id
        call_id_pattern = re.compile(r'^(\d+)-(.*)\.([a-z0-9]+)')
        result = call_id_pattern.findall(raw_call)
        # Return if call id not found
        if len(result) != 1:
            return
        result = result[0]
        if len(result) != 3:
            return
        # Store results
        call_id = result[0]
        raw_refs = result[1]
        ext = result[2]
        # Match shader refs
        shaders_pattern = re.compile(r'-([a-z]s=[a-f0-9]+)')
        raw_shaders_refs = shaders_pattern.findall(raw_refs)
        # Return if no shader refs found
        if len(raw_shaders_refs) < 1:
            return
        # Remove shaders refs from the raw string
        # Only resource ref should be left in raw string at this point
        raw_resource_ref = re.sub(shaders_pattern, '', raw_refs)

        self.call_id = call_id
        self.ext = ext
        self.parse_raw_resource_ref(raw_resource_ref)
        self.parse_raw_shader_refs(raw_shaders_refs)

    def parse_raw_resource_ref(self, raw_resource_ref):
        result = raw_resource_ref.split('=')

        if len(result) == 0:
            return

        if len(result) == 2:
            raw_hash = result[1]
            # Handle `texture_hash = 1` 3dm setting, resulting in names like `000003-ps-t1=0dbc4afc(5e9494f3)-vs=2fb5a3f559d5a6f9-ps=561bcd63f5b5531a`
            hashes = raw_hash.split('(')
            # Actual hash
            self.hash = hashes[0]
            # Hash that texture would have without `texture_hash = 1` enabled
            if len(hashes) > 1:
                self.old_hash = hashes[1].replace(')', '')
        else:
            self.hash = None

        resource_desc = result[0].split('-')

        if len(resource_desc) == 1:
            self.parse_raw_slot_ref(resource_desc[0], None)
        else:
            self.parse_raw_slot_ref(resource_desc[1], resource_desc[0])

    def parse_raw_slot_ref(self, raw_slot_ref, raw_shader_type):
        slot_ref_pattern = re.compile(r'^([a-z]+)([0-9]+)?')
        result = slot_ref_pattern.findall(raw_slot_ref)
        if len(result) != 1:
            return
        result = result[0]
        self.slot_type = slot_type_codepage.get(result[0], None)
        if self.slot_type is None:
            raise ValueError(f'Failed to parse slot ref "{raw_slot_ref}": slot type not recognized!')
        if len(result) == 2 and result[1] != '':
            self.slot_id = int(result[1])
        if raw_shader_type is not None:
            self.slot_shader_type = shader_type_codepage.get(raw_shader_type, None)
            if self.slot_shader_type is None:
                raise ValueError(f'Failed to parse slot shader type "{raw_shader_type}": shader type not recognized!')

    def parse_raw_shader_refs(self, raw_shader_refs):
        for raw_shader_ref in raw_shader_refs:
            self.shaders.append(ShaderRef(raw_shader_ref))

    def copy_file(self, dest_path):
        shutil.copyfile(self.path, dest_path)


class CallDescriptor:
    def __init__(self, call_id):
        self.id = call_id
        self.parameters = {}
        self.shaders = {}
        self.resources = {}

    def import_resource_descriptor(self, resource_descriptor):
        if resource_descriptor.call_id != self.id:
            raise ValueError(f'Failed to import resource descriptor {resource_descriptor.raw}: call id mismatch!')
        if resource_descriptor.ext == 'txt':
            return
        for shader in resource_descriptor.shaders:
            self.shaders[shader.raw] = shader

        self.resources[resource_descriptor.raw] = resource_descriptor

    def hash_resources(self):
        for resource in self.resources:
            resource.hash_data()

    def get_filtered_resources(self, filter_attributes):
        resource_filter = Filter(
            condition=FilterCondition.AND,
            attributes_condition=FilterCondition.AND,
            attributes=filter_attributes,
            dictionaries_condition=FilterCondition.AND,
            dictionaries=[
                self.resources
            ]
        )
        return DictFilter(resource_filter).filtered_dict

    def get_filtered_resource(self, filter_attributes):
        result = self.get_filtered_resources(filter_attributes)
        if len(result) == 1:
            return next(iter(result.values()))
        elif len(result) == 0:
            return None
        else:
            raise ValueError(f'Found more than 1 resource with provided attributes!')

    def __repr__(self):
        return f'{self.id}, {", ".join(self.shaders.keys())}'