import re
import bpy

from typing import List, Dict, Union
from dataclasses import dataclass, field
from enum import Enum
from textwrap import dedent

from ..addon.exceptions import ConfigError

from ..migoto_io.blender_interface.collections import *
from ..migoto_io.blender_interface.objects import *

from ..migoto_io.blender_tools.modifiers import apply_modifiers_for_object_with_shape_keys
from ..migoto_io.blender_tools.vertex_groups import fill_gaps_in_vertex_groups

from ..extract_frame_data.metadata_format import ExtractedObject


class SkeletonType(Enum):
    Merged = 'Merged'
    PerComponent = 'Per-Component'


@dataclass
class TempObject:
    name: str
    object: bpy.types.Object
    vertex_count: int = 0
    index_count: int = 0
    index_offset: int = 0


@dataclass
class MergedObjectComponent:
    objects: List[TempObject]
    vertex_count: int = 0
    index_count: int = 0
    blend_remap_id: int = -1
    blend_remap_vg_count: int = 0
    
    def get_object(self, object_name):
        for obj in self.objects:
            if obj.name == object_name:
                return obj


@dataclass
class MergedObjectShapeKeys:
    vertex_count: int = 0


@dataclass
class MergedObject:
    object: bpy.types.Object
    mesh: bpy.types.Mesh
    components: List[MergedObjectComponent]
    shapekeys: MergedObjectShapeKeys
    skeleton_type: SkeletonType
    vertex_count: int = 0
    index_count: int = 0
    vg_count: int = 0
    blend_remap_count: int = 0


@dataclass
class ObjectMerger:
    # Input
    context: bpy.types.Context
    extracted_object: ExtractedObject
    ignore_nested_collections: bool
    ignore_hidden_collections: bool
    ignore_hidden_objects: bool
    ignore_muted_shape_keys: bool
    apply_modifiers: bool
    collection: str
    skeleton_type: SkeletonType
    mesh_scale: float = 1.0
    mesh_rotation: Tuple[float] = (0.0, 0.0, 0.0)
    add_missing_vertex_groups: bool = False
    # Output
    merged_object: MergedObject = field(init=False)

    def __post_init__(self):
        collection_was_hidden = collection_is_hidden(self.collection)
        unhide_collection(self.collection)

        self.initialize_components()
        try:
            self.import_objects_from_collection()
            self.prepare_temp_objects()
            self.build_merged_object()
        except Exception as e:
            self.remove_temp_objects()
            raise e
        
        if collection_was_hidden:
            hide_collection(self.collection)

    def initialize_components(self):
        self.components = []
        for component_id, component in enumerate(self.extracted_object.components): 
            self.components.append(
                MergedObjectComponent(
                    objects=[],
                    index_count=0,
                )
            )

    def import_objects_from_collection(self):

        num_objects = 0
        
        component_pattern = re.compile(r'.*component[_ -]*(\d+).*')

        for obj in get_collection_objects(self.collection, 
                                          recursive = not self.ignore_nested_collections, 
                                          skip_hidden_collections = self.ignore_hidden_collections):

            if self.ignore_hidden_objects and object_is_hidden(obj):
                continue

            if obj.name.startswith('TEMP_'):
                continue
            
            match = component_pattern.findall(obj.name.lower())
            if len(match) == 0:
                continue
            component_id = int(match[0])

            if component_id >= len(self.components):
                raise ConfigError('object_source_folder', f'Metadata.json in specified folder is missing Component {component_id}!\nMost likely it contains sources for other object.')

            temp_obj = copy_object(self.context, obj, name=f'TEMP_{obj.name}', collection=self.collection)

            self.components[component_id].objects.append(TempObject(
                name=obj.name,
                object=temp_obj,
            ))

            num_objects += 1

        if num_objects == 0:
            raise ValueError(f'No eligible `Component` objects found!')

    def prepare_temp_objects(self):

        index_offset = 0

        for component_id, component in enumerate(self.components):

            component.objects.sort(key=lambda x: x.name)

            for temp_object in component.objects:
                temp_obj = temp_object.object
                # Remove muted shape keys
                if self.ignore_muted_shape_keys and temp_obj.data.shape_keys:
                    muted_shape_keys = []
                    for shapekey_id in range(len(temp_obj.data.shape_keys.key_blocks)):
                        shape_key = temp_obj.data.shape_keys.key_blocks[shapekey_id]
                        if shape_key.mute:
                            muted_shape_keys.append(shape_key)
                    for shape_key in muted_shape_keys:
                        temp_obj.shape_key_remove(shape_key)
                # Modify temporary object
                with OpenObject(self.context, temp_obj, mode='OBJECT') as obj:
                    # Apply all transforms
                    bpy.ops.object.transform_apply(location = True, rotation = True, scale = True)
                    # Apply all modifiers
                    if self.apply_modifiers:
                        selected_modifiers = [modifier.name for modifier in get_modifiers(obj)]
                        apply_modifiers_for_object_with_shape_keys(self.context, selected_modifiers, None)
                    # Triangulate (this step is crucial since export supports only triangles)
                    triangulate_object(self.context, temp_obj)
                # Handle Vertex Groups
                vertex_groups = get_vertex_groups(temp_obj)
                # Fill gaps in Vertex Groups list based on VG names (i.e. add group '1' between '0' and '2' if it's missing)
                if self.add_missing_vertex_groups:
                    fill_gaps_in_vertex_groups(self.context, temp_obj, internal_call=True)
                # Remove ignored or unexpected vertex groups
                if self.skeleton_type == SkeletonType.Merged:
                    # Exclude VGs with 'ignore' tag or with higher VG id than total VG count from Metadata.ini
                    total_vg_count = sum([component.vg_count for component in self.extracted_object.components])
                    ignore_list = [vg for vg in vertex_groups if 'ignore' in vg.name.lower() or vg.index >= total_vg_count]
                elif self.skeleton_type == SkeletonType.PerComponent:
                    # Exclude VGs with 'ignore' tag or with higher id VG count from Metadata.ini for current component
                    extracted_component = self.extracted_object.components[component_id]
                    total_vg_count = len(extracted_component.vg_map)
                    ignore_list = [vg for vg in vertex_groups if 'ignore' in vg.name.lower() or vg.index >= total_vg_count]
                remove_vertex_groups(temp_obj, ignore_list)
                # Rename VGs to their indicies to merge ones of different components together
                for vg in get_vertex_groups(temp_obj):
                    vg.name = str(vg.index)
                # Calculate vertex count of temporary object
                temp_object.vertex_count = len(temp_obj.data.vertices)
                # Calculate index count of temporary object, IB stores 3 indices per triangle
                temp_object.index_count = len(temp_obj.data.polygons) * 3
                # Set index offset of temporary object to global index_offset
                temp_object.index_offset = index_offset
                # Update global index_offset
                index_offset += temp_object.index_count
                # Update vertex and index count of custom component
                component.vertex_count += temp_object.vertex_count
                component.index_count += temp_object.index_count

    def remove_temp_objects(self):
        for component_id, component in enumerate(self.components):
            for temp_object in component.objects:
                remove_mesh(temp_object.object.data)

    def transform_merged_object(self, merged_object):
        change_scale = self.mesh_scale != 1.0
        change_rotation = self.mesh_rotation != (0.0, 0.0, 0.0)
        if not change_scale and not change_rotation:
            return
        # Compensate transforms we're about to set
        if change_scale:
            inverted_scale = 1 / self.mesh_scale
            merged_object.scale = inverted_scale, inverted_scale, inverted_scale
        if change_rotation:
            inverted_rotation = tuple([360 - r if r != 0 and r != 0 else 0 for r in self.mesh_rotation])
            merged_object.rotation_euler = to_radians(inverted_rotation)
        bpy.ops.object.transform_apply(location = False, rotation = True, scale = True)
        # Set merged object transforms
        if change_scale:
            merged_object.scale = self.mesh_scale, self.mesh_scale, self.mesh_scale
        if change_rotation:
            merged_object.rotation_euler = to_radians(self.mesh_rotation)

    def build_merged_object(self):

        merged_object = []
        vertex_count, index_count = 0, 0
        for component in self.components:
            for temp_object in component.objects:
                merged_object.append(temp_object.object)
            vertex_count += component.vertex_count
            index_count += component.index_count
            
        join_objects(self.context, merged_object)

        obj = merged_object[0]

        rename_object(obj, 'TEMP_EXPORT_OBJECT')

        deselect_all_objects()
        select_object(obj)
        set_active_object(bpy.context, obj)
        
        self.transform_merged_object(obj)

        mesh = obj.evaluated_get(self.context.evaluated_depsgraph_get()).to_mesh()

        self.merged_object = MergedObject(
            object=obj,
            mesh=mesh,
            components=self.components,
            vertex_count=len(obj.data.vertices),
            index_count=len(obj.data.polygons) * 3,
            vg_count=len(get_vertex_groups(obj)),
            shapekeys=MergedObjectShapeKeys(),
            skeleton_type=self.skeleton_type,
        )

        if vertex_count != self.merged_object.vertex_count:
            raise ValueError('vertex_count mismatch between merged object and its components')

        if index_count != self.merged_object.index_count:
            raise ValueError('index_count mismatch between merged object and its components')
