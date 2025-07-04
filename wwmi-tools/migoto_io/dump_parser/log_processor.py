import os
import re

from enum import Enum, auto
from dataclasses import dataclass
from pathlib import Path

class ShaderType(Enum):
    Empty = 'null'
    Any = 'any'
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

@dataclass
class Dispatch:
    ThreadGroupCountX: int
    ThreadGroupCountY: int
    ThreadGroupCountZ: int


@dataclass
class DrawIndexed:
    IndexCount: int
    StartIndexLocation: int
    BaseVertexLocation: int


class CommandType(Enum):

    CSSetShader = 'CSSetShader'
    VSSetShader = 'VSSetShader'
    PSSetShader = 'PSSetShader'
    GSSetShader = 'GSSetShader'
    HSSetShader = 'HSSetShader'
    DSSetShader = 'DSSetShader'

    CSSetShaderResources = 'CSSetShaderResources'
    VSSetShaderResources = 'VSSetShaderResources'
    PSSetShaderResources = 'PSSetShaderResources'
    GSSetShaderResources = 'GSSetShaderResources'
    HSSetShaderResources = 'HSSetShaderResources'
    DSSetShaderResources = 'DSSetShaderResources'

    CSSetUnorderedAccessViews = 'CSSetUnorderedAccessViews'

    CSSetConstantBuffers = 'CSSetConstantBuffers'
    VSSetConstantBuffers = 'VSSetConstantBuffers'
    PSSetConstantBuffers = 'PSSetConstantBuffers'
    GSSetConstantBuffers = 'GSSetConstantBuffers'
    HSSetConstantBuffers = 'HSSetConstantBuffers'
    DSSetConstantBuffers = 'DSSetConstantBuffers'

    IASetIndexBuffer = 'IASetIndexBuffer'
    IASetVertexBuffers = 'IASetVertexBuffers'

    SOSetTargets = 'SOSetTargets'
    CopyResource = 'CopyResource'

    Dispatch = 'Dispatch'
    DrawIndexedInstanced = 'DrawIndexedInstanced'
    DrawIndexed = 'DrawIndexed'
    Draw = 'Draw'


class ContextType(Enum):
    Empty = auto()
    NewCall = auto()
    CurrentCall = auto()
    CurrentCommand = auto()


class FrameDumpCall:
    def __init__(self, call_id):
        self.id = call_id
        self.parameters = {}
        self.output_resources = []

@dataclass
class FrameDumpShader:
    type: ShaderType
    pointer: str
    hash: str
    last_set_call_id: int = -1


@dataclass
class FrameDumpResource:
    pointer: str
    hash: str
    last_set_call_id: int


class FrameDumpModel:
    def __init__(self):
        self.call = None
        self.calls = None
        self.current_shaders = {
            ShaderType.Compute: None,
            ShaderType.Vertex: None,
            ShaderType.Pixel: None,
            ShaderType.Geometry: None,
            ShaderType.Hull: None,
            ShaderType.Domain: None,
        }
        self.current_resources = {
            ShaderType.Compute: {
                SlotType.ConstantBuffer: [None] * 16,
                SlotType.Texture: [None] * 128,
                SlotType.UAV: [None] * 8,
            },
            ShaderType.Vertex: {
                SlotType.ConstantBuffer: [None] * 16,
                SlotType.IndexBuffer: [None],
                SlotType.VertexBuffer: [None] * 32,
                SlotType.Texture: [None] * 128,
            },
            ShaderType.Pixel: {
                SlotType.ConstantBuffer: [None] * 16,
                SlotType.Texture: [None] * 128,
                SlotType.RenderTarget: [None] * 8,
            },
            ShaderType.Geometry: {
                SlotType.ConstantBuffer: [None] * 16,
                SlotType.Texture: [None] * 128,
            },
            ShaderType.Hull: {
                SlotType.ConstantBuffer: [None] * 16,
                SlotType.Texture: [None] * 128,
            },
            ShaderType.Domain: {
                SlotType.ConstantBuffer: [None] * 16,
                SlotType.Texture: [None] * 128,
            },
        }
        self.shaders = {}
        self.resources = {}
        self.resource_copies = {}

    def get_shader(self, pointer):
        return self.shaders.get(pointer, None)

    def set_shader(self, shader_type, pointer, hash):
        shader = FrameDumpShader(shader_type, pointer, hash, self.call.id)
        self.shader[pointer] = shader
        return shader

    def get_current_shader(self, shader_type):
        return self.current_resources[shader_type]

    def set_current_shader(self, shader_type, pointer, hash):
        shader = self.get_shader(pointer)
        if shader is None:
            shader = self.set_shader(shader_type, pointer, hash)
            self.shader[pointer] = shader
        self.current_shaders[shader_type] = shader
        return shader

    def clear_current_shader(self, shader_type):
        self.current_shaders[shader_type] = None

    def get_resource(self, pointer):
        return self.resources.get(pointer, None)

    def set_resource(self, pointer, hash):
        resource = FrameDumpResource(pointer, hash, self.call.id)
        self.resources[pointer] = resource
        return resource

    def get_current_resource(self, shader_type, slot_type, slot_id):
        return self.current_resources[shader_type][slot_type][slot_id]

    def set_current_resource(self, shader_type, slot_type, slot_id, pointer, hash):
        resource = self.get_resource(pointer)
        if resource is None:
            resource = self.set_resource(pointer, hash)
        self.current_resources[shader_type][slot_type][slot_id] = resource
        return resource

    def clear_current_resource(self, shader_type, slot_type, slot_id):
        self.current_resources[shader_type][slot_type][slot_id] = None


class FrameDumpLogProcessor:
    def __init__(self, dump_path):
        self.path = os.path.join(dump_path, 'log.txt')
        self.current_command = None
        self.model = FrameDumpModel()

        self.command_handlers = {
            CommandType.CSSetConstantBuffers: (self.handle_set_constant_buffers, ShaderType.Compute),
            CommandType.VSSetConstantBuffers: (self.handle_set_constant_buffers, ShaderType.Vertex),
            CommandType.PSSetConstantBuffers: (self.handle_set_constant_buffers, ShaderType.Pixel),
            CommandType.GSSetConstantBuffers: (self.handle_set_constant_buffers, ShaderType.Geometry),
            CommandType.HSSetConstantBuffers: (self.handle_set_constant_buffers, ShaderType.Hull),
            CommandType.DSSetConstantBuffers: (self.handle_set_constant_buffers, ShaderType.Domain),

            CommandType.CSSetShaderResources: (self.handle_set_current_resources, ShaderType.Compute),
            CommandType.VSSetShaderResources: (self.handle_set_current_resources, ShaderType.Vertex),
            CommandType.PSSetShaderResources: (self.handle_set_current_resources, ShaderType.Pixel),
            CommandType.GSSetShaderResources: (self.handle_set_current_resources, ShaderType.Geometry),
            CommandType.HSSetShaderResources: (self.handle_set_current_resources, ShaderType.Hull),
            CommandType.DSSetShaderResources: (self.handle_set_current_resources, ShaderType.Domain),

            CommandType.CSSetShader: (self.handle_set_current_shader, ShaderType.Compute),
            CommandType.VSSetShader: (self.handle_set_current_shader, ShaderType.Vertex),
            CommandType.PSSetShader: (self.handle_set_current_shader, ShaderType.Pixel),
            CommandType.GSSetShader: (self.handle_set_current_shader, ShaderType.Geometry),
            CommandType.HSSetShader: (self.handle_set_current_shader, ShaderType.Hull),
            CommandType.DSSetShader: (self.handle_set_current_shader, ShaderType.Domain),

            CommandType.IASetIndexBuffer: (self.handle_ia_set_index_buffer, ShaderType.Vertex),
            CommandType.IASetVertexBuffers: (self.handle_ia_set_vertex_buffers, ShaderType.Vertex),
            CommandType.CSSetUnorderedAccessViews: (self.handle_cs_set_unordered_access_views, ShaderType.Compute),
            
            CommandType.CopyResource: (self.handle_copy_resource, ShaderType.Any),
            CommandType.SOSetTargets: (self.handle_so_set_targets, ShaderType.Any),
            
            CommandType.Dispatch: (self.handle_dispatch, ShaderType.Compute),
            CommandType.DrawIndexedInstanced: (self.handle_draw_indexed_instanced, ShaderType.Vertex),
            CommandType.DrawIndexed: (self.handle_draw_indexed, ShaderType.Vertex),
            CommandType.Draw: (self.handle_draw, ShaderType.Vertex),
        }
        self.command_entry_handlers = {
            CommandType.CSSetConstantBuffers: (self.handle_set_constant_buffers_entry, ShaderType.Compute),
            CommandType.VSSetConstantBuffers: (self.handle_set_constant_buffers_entry, ShaderType.Vertex),
            CommandType.PSSetConstantBuffers: (self.handle_set_constant_buffers_entry, ShaderType.Pixel),
            CommandType.GSSetConstantBuffers: (self.handle_set_constant_buffers_entry, ShaderType.Geometry),
            CommandType.HSSetConstantBuffers: (self.handle_set_constant_buffers_entry, ShaderType.Hull),
            CommandType.DSSetConstantBuffers: (self.handle_set_constant_buffers_entry, ShaderType.Domain),

            CommandType.CSSetShaderResources: (self.handle_set_current_resources_entry, ShaderType.Compute),
            CommandType.VSSetShaderResources: (self.handle_set_current_resources_entry, ShaderType.Vertex),
            CommandType.PSSetShaderResources: (self.handle_set_current_resources_entry, ShaderType.Pixel),
            CommandType.GSSetShaderResources: (self.handle_set_current_resources_entry, ShaderType.Geometry),
            CommandType.HSSetShaderResources: (self.handle_set_current_resources_entry, ShaderType.Hull),
            CommandType.DSSetShaderResources: (self.handle_set_current_resources_entry, ShaderType.Domain),

            CommandType.IASetVertexBuffers: (self.handle_ia_set_vertex_buffers_entry, ShaderType.Any),
            CommandType.CSSetUnorderedAccessViews: (self.handle_cs_set_unordered_access_views_entry, ShaderType.Compute),

            CommandType.CopyResource: (self.handle_copy_resource_entry, ShaderType.Any),
            CommandType.SOSetTargets: (self.handle_so_set_targets_entry, ShaderType.Any),
        }

        self.parse_log()
        self.validate()

    def validate(self):
        pass

    def parse_log(self):
        self.calls = {}
        with (open(self.path, "r") as f):
            for line_id, line in enumerate(f.readlines()):
                # try:
                context_type = self.handle_call_id(line[0:6])
                if context_type == ContextType.CurrentCall:
                    self.handle_new_command(line[7:].strip())
                elif context_type == ContextType.CurrentCommand:
                    self.handle_command_entry(line.strip())
                # except ValueError as e:
                    # raise ValueError(f'[Log Parser][log.txt:{line_id}] Error: {e}')

    def handle_call_id(self, call_id):
        if call_id.isnumeric():
            call_id = int(call_id)
            if self.call is not None and call_id == self.call.id:
                return ContextType.CurrentCall
            self.call = FrameDumpCall(call_id)
            if call_id in self.calls:
                raise ValueError(f'data collection for call id {call_id} is already finished, current call id: {self.call.id}')
            self.calls[call_id] = self.call
            return ContextType.CurrentCall
        elif self.call is None:
            return ContextType.Empty
        else:
            return ContextType.CurrentCommand
        
    def handle_new_command(self, line):
        self.current_command = None
        for command, (command_handler, shader_type) in self.command_handlers.items():
            if line.startswith(command.value):
                self.current_command = command
                command_handler(shader_type, line)
                return
            
        # raise ValueError(f'unknown command {line}')
        ignore = ['Map', 'Unmap', 'GetData', 'IASetInputLayout', 'OMGetDepthStencilState', 
                  'RSSetViewports', 'PSSetSamplers', 'RSSetState', 'OMSetBlendState', 'OMSetRenderTargets', 
                  'ClearRenderTargetView', 'ClearDepthStencilView', 'End', 'CopySubresourceRegion', 'CSSetSamplers', 
                  'OMSetDepthStencilState', 'IASetPrimitiveTopology', '3DMigoto', 'UpdateSubresource', 'VSSetSamplers',
                  'RSSetScissorRects', 'OMGetRenderTargets', 'Begin']
        for cmd in ignore:
            if line.startswith(cmd):
                return
        print(f'unknown command {line}')

    def handle_command_entry(self, line):
        params = self.command_entry_handlers.get(self.current_command, None)
        if params is not None:
            (command_entry_handler, shader_type) = params
            command_entry_handler(shader_type, line)
        # else:
        #     raise ValueError(f'no handler for command {self.current_command} entry {line}')

    # Command handlers

    def handle_dispatch(self, shader_type, line):
        '''
        Expected command format:
            Dispatch(ThreadGroupCountX:2, ThreadGroupCountY:1, ThreadGroupCountZ:1)
        '''
        pattern = re.compile(r'ThreadGroupCountX:(\d+), ThreadGroupCountY:(\d+), ThreadGroupCountZ:(\d+)')
        data = self.extract_data(line, pattern)
        self.call.parameters[CommandType.Dispatch] = Dispatch(int(data[0]), int(data[1]), int(data[2]))

    def handle_draw_indexed(self, shader_type, line):
        '''
        Expected command format:
            DrawIndexed(IndexCount:6966, StartIndexLocation:0, BaseVertexLocation:0)
        '''
        pattern = re.compile(r'IndexCount:(\d+), StartIndexLocation:(\d+), BaseVertexLocation:(\d+)')
        data = self.extract_data(line, pattern)
        self.call.parameters[CommandType.DrawIndexed] = DrawIndexed(int(data[0]), int(data[1]), int(data[2]))

    def handle_draw_indexed_instanced(self, shader_type, line):
        pass
    
    def handle_draw(self, shader_type, line):
        pass

    def handle_copy_resource(self, shader_type, line):
        '''
        Expected format:
            CopyResource(pDstResource:0x000001ED0D731CF8, pSrcResource:0x000001ED5B6B6DB8)
        '''
        pattern = re.compile(r'pDstResource:(0x[0-9a-fA-F]+), pSrcResource:(0x[0-9a-fA-F]+)')
        data = self.extract_data(line, pattern)
        self.resource_copies[data[0]] = data[1]

    def handle_so_set_targets(self, shader_type, line):
        '''
        Expected format:
            SOSetTargets(NumBuffers:1, ppSOTargets:0x000000BD5846E260, pOffsets:0x000000BD5846E250)
        '''
        pattern = re.compile(r'NumBuffers:(\d+), ppSOTargets:(0x[0-9a-fA-F]+), pOffsets:(0x[0-9a-fA-F]+)')
        data = self.extract_data(line, pattern)

    def handle_set_current_shader(self, shader_type, line):
        '''
        Expected format:
            CSSetShader(pComputeShader:0x000001ECFC102310, ppClassInstances:0x0000000000000000, NumClassInstances:0) hash=743108cc03f39cbf
        '''
        pattern = re.compile(r'p\w*Shader:(0x[0-9a-fA-F]+), ppClassInstances:0x[0-9a-fA-F]+, NumClassInstances:\d+(?:.* hash=)?([0-9a-fA-F]+)?')
        data = self.extract_data(line, pattern)
        if len(data) == 2:
            shader_pointer, shader_hash = data[0], data[1]
            if shader_pointer != '0x0000000000000000':
                self.model.set_current_shader(shader_type, shader_pointer, shader_hash)
            else:
                self.model.clear_current_shader(shader_type)
        elif len(data) == 1:
            self.model.clear_current_shader(shader_type)
        else:
            raise ValueError(f'malformed SetShader command: {line}')

    def handle_set_current_resources(self, shader_type, line):
        '''
        Expected format:
            CSSetShaderResources(StartSlot:0, NumViews:1, ppShaderResourceViews:0x000000BD5846E248)
        '''
        pattern = re.compile(r'StartSlot:(\d+), NumViews:(\d+), ppShaderResourceViews:(0x[0-9a-fA-F]+)')
        data = self.extract_data(line, pattern)
        if len(data) == 3:
            start_slot, num_views, resource_views_pointer = int(data[0]), int(data[1]), data[2]
            for slot_id in range(start_slot, start_slot + num_views):
                self.model.clear_current_resource(shader_type, SlotType.Texture, slot_id)
        else:
            raise ValueError(f'malformed SetShaderResources command: {line}')

    def handle_set_constant_buffers(self, shader_type, line):
        '''
        Expected format:
            VSSetConstantBuffers1(StartSlot:2, NumBuffers:1, ppConstantBuffers:0x000000BD5846C5F8, pFirstConstant:0x000000BD5846C5D0, pNumConstants:0x000000BD5846C5F0)
        '''
        pattern = re.compile(r'StartSlot:(\d+), NumBuffers:(\d+), ppConstantBuffers:(0x[0-9a-fA-F]+)')
        data = self.extract_data(line, pattern)
        if len(data) == 3:
            start_slot, num_buffers, resource_views_pointer = int(data[0]), int(data[1]), data[2]
            for slot_id in range(start_slot, start_slot + num_buffers):
                self.model.clear_current_resource(shader_type, SlotType.ConstantBuffer, slot_id)
        else:
            raise ValueError(f'malformed SetConstantBuffers command: {line}')

    def handle_ia_set_index_buffer(self, shader_type, line):
        '''
        Expected format:
            IASetIndexBuffer(pIndexBuffer:0x000001ED5C1A1AF8, Format:57, Offset:0) hash=e07d9851
        '''
        pattern = re.compile(r'pIndexBuffer:(0x[0-9a-fA-F]+), Format:(\d+), Offset:(\d+)(?:.*hash=)?([0-9a-fA-F]+)?')
        data = self.extract_data(line, pattern)
        if len(data) == 4:
            pointer, format, offset, ib_hash = data[0], data[1], data[2], data[3]
            self.model.set_current_resource(shader_type, SlotType.IndexBuffer, 0, pointer, ib_hash)
        elif len(data) == 3:
            self.model.clear_current_resource(shader_type, SlotType.IndexBuffer, 0)
        else:
            raise ValueError(f'malformed IASetIndexBuffer command: {line}')

    def handle_ia_set_vertex_buffers(self, shader_type, line):
        '''
        Expected format:
            IASetVertexBuffers(StartSlot:0, NumBuffers:3, ppVertexBuffers:0x000000BD5846E1C0, pStrides:0x000000BD5846E1A0, pOffsets:0x000000BD5846E180)
        '''
        pattern = re.compile(r'StartSlot:(\d+), NumBuffers:(\d+), ppVertexBuffers:(0x[0-9a-fA-F]+)')
        data = self.extract_data(line, pattern)
        if len(data) == 3:
            start_slot, num_buffers, resource_views_pointer = int(data[0]), int(data[1]), data[2]
            for slot_id in range(start_slot, start_slot + num_buffers):
                self.model.clear_current_resource(shader_type, SlotType.VertexBuffer, slot_id)
        else:
            raise ValueError(f'malformed IASetVertexBuffers command: {line}')
        
    def handle_cs_set_unordered_access_views(self, shader_type, line):
        '''
        Expected format:
            CSSetUnorderedAccessViews(StartSlot:0, NumUAVs:1, ppUnorderedAccessViews:0x000000BD5846E250, pUAVInitialCounts:0x000000BD5846E248)
        '''
        pattern = re.compile(r'StartSlot:(\d+), NumUAVs:(\d+), ppUnorderedAccessViews:(0x[0-9a-fA-F]+)')
        data = self.extract_data(line, pattern)
        if len(data) == 3:
            start_slot, num_buffers, views = int(data[0]), int(data[1]), data[2]
            for slot_id in range(start_slot, start_slot + num_buffers):
                self.model.clear_current_resource(shader_type, SlotType.UAV, slot_id)
        else:
            raise ValueError(f'malformed CSSetUnorderedAccessViews command: {line}')

    # Command entry handlers

    def handle_copy_resource_entry(self, shader_type, line):
        '''
        Expected format:
            Src: resource=0x000001ED5B6B6DB8 hash=6590112a
            Dst: resource=0x000001ED0D731CF8 hash=2f103f55
        '''
        pattern = re.compile(r'(\w+): resource=(0x[0-9a-fA-F]+)(?:.* hash=)?([0-9a-fA-F]+)?')
        data = self.extract_data(line, pattern)
        if data[0] == 'Src':
            if not data[1] in self.resources:
                self.resources[data[1]] = FrameDumpResource(data[1], data[2])
        elif data[0] == 'Dst':
            self.resources[data[1]] = FrameDumpResource(data[1], data[2])
        else:
            raise ValueError(f'malformed CopyResource entry {line}')

    def handle_so_set_targets_entry(self, shader_type, line):
        '''
        Expected format:
            0: resource=0x000001ED7B87B378 hash=416ae3b3
        '''
        pattern = re.compile(r'(\d+): resource=(0x[0-9a-fA-F]+).* hash=([0-9a-fA-F]+)')
        data = self.extract_data(line, pattern)
        if len(data) == 2:
            resource = FrameDumpResource(data[1], data[2])
            self.resources[data[1]] = resource
            self.call.output_resources.append(resource)
        else:
            raise ValueError(f'malformed SOSetTargets command entry {line}')

    def handle_set_current_resources_entry(self, shader_type, line):
        '''
        Expected format:
            view=0x000001ECFC146C40 resource=0x000001ED5C173938 hash=84529dab
        '''
        pattern = re.compile(r'(\d+): view=(0x[0-9a-fA-F]+) resource=(0x[0-9a-fA-F]+) hash=([0-9a-fA-F]+)')
        data = self.extract_data(line, pattern)
        if len(data) == 4:
            slot_id, view, pointer, texture_hash = int(data[0]), data[1], data[2], data[3]
            self.model.set_current_resource(shader_type, SlotType.Texture, slot_id, pointer, texture_hash)
        else:
            raise ValueError(f'malformed SetShaderResources command entry {line}')

    def handle_set_constant_buffers_entry(self, shader_type, line):
        '''
        Expected format:
            1: resource=0x000001ECE165C2B8 hash=f24bbeee
        '''
        pattern = re.compile(r'(\d+): resource=(0x[0-9a-fA-F]+) hash=([0-9a-fA-F]+)')
        data = self.extract_data(line, pattern)
        if len(data) == 3:
            slot_id, pointer, cb_hash = int(data[0]), data[1], data[2]
            self.model.set_current_resource(shader_type, SlotType.ConstantBuffer, slot_id, pointer, cb_hash)
        else:
            raise ValueError(f'malformed SetConstantBuffers command entry {line}')

    def handle_ia_set_vertex_buffers_entry(self, shader_type, line):
        '''
        Expected format:
            0: resource=0x000001ED37DCFB78 hash=960479aa
        '''
        pattern = re.compile(r'(\d+): resource=(0x[0-9a-fA-F]+) hash=([0-9a-fA-F]+)')
        data = self.extract_data(line, pattern)
        if len(data) == 3:
            slot_id, pointer, vb_hash = int(data[0]), data[1], data[2]
            self.model.set_current_resource(shader_type, SlotType.VertexBuffer, slot_id, pointer, vb_hash)
        else:
            raise ValueError(f'malformed IASetVertexBuffers command entry {line}')

    def handle_cs_set_unordered_access_views_entry(self, shader_type, line):
        '''
        Expected format:
            0: view=0x000001ED1D4188D0 resource=0x000001ED0D731CF8 hash=2f103f55
        '''
        pattern = re.compile(r'(\d+): view=(0x[0-9a-fA-F]+) resource=(0x[0-9a-fA-F]+) hash=([0-9a-fA-F]+)')
        data = self.extract_data(line, pattern)
        if len(data) == 4:
            slot_id, view, pointer, uav_hash = int(data[0]), data[1], data[2], data[3]
            self.model.set_current_resource(shader_type, SlotType.UAV, slot_id, pointer, uav_hash)
        else:
            raise ValueError(f'malformed CSSetUnorderedAccessViews command entry {line}')

    @staticmethod
    def extract_data(line, pattern):
        result = pattern.findall(line)
        if len(result) != 1:
            raise ValueError(f'pattern {pattern} failed to match line {line}')
        return result[0]



if __name__ == '__main__':
    FrameDumpLogProcessor(Path(r'C:\Projects\ZZZ\WWMI-For-Modders\FrameAnalysis-2024-07-04-174943'))  # ZZZ
    # FrameDumpLogProcessor(Path(r'C:\Projects\Wuthering Waves\WWMI_DEV\FrameAnalysis-2024-07-01-072108'))  # WuWa

    print(1)