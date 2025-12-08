import json
import bpy
import numpy

from typing import List, Dict, Union
from dataclasses import dataclass, field
from enum import Enum

from ..blender_interface.collections import *
from ..blender_interface.objects import *
        

def create_merged_object(context):

    if len(context.selected_objects) < 2:
        raise ValueError(f'Less than 2 objects selected!')

    col = context.selected_objects[0].users_collection[0]

    # Duplicate selected objects and join copies
    vertex_counts = {}
    temp_objects = []
    for obj in context.selected_objects:
        vertex_counts[obj.name] = len(obj.data.vertices)
        temp_objects.append(copy_object(context, obj, name=f'TEMP_{obj.name}', collection=col))
    join_objects(context, temp_objects)

    merged_obj = temp_objects[0]
    rename_object(merged_obj, 'MERGED_OBJECT')

    # Store vertex counts of each object so we could decompose merged object data later
    merged_obj['WWMI:MergedObjectComponents'] = json.dumps(vertex_counts)

    deselect_all_objects()
    select_object(merged_obj)
    set_active_object(bpy.context, merged_obj)

    # Set Basis as active shapekey if it exists (Blender tends to "forget" to do it and sculpt data goes to mesh.vertices lol)
    if merged_obj.data.shape_keys is not None and len(getattr(merged_obj.data.shape_keys, 'key_blocks', [])) > 0:
        key_blocks = merged_obj.data.shape_keys.key_blocks
        basis = key_blocks.get("Basis")
        if basis:
            index = list(key_blocks).index(basis)
            merged_obj.active_shape_key_index = index


def transfer_position_data(context, apply_deltas_to_shapekeys = False):

    # Try to use active object from sculpt mode
    merged_obj = bpy.context.active_object
    if not merged_obj or not merged_obj.mode == 'SCULPT':
        # Fall back to selected object
        if len(context.selected_objects) < 1:
            raise ValueError(f'No object selected!')
        merged_obj = context.selected_objects[0]

    merged_object_components = merged_obj.get('WWMI:MergedObjectComponents', None)

    if merged_object_components is None:
        raise ValueError(f'Object is missing WWMI:MergedObjectComponents atribute!')

    vertex_counts = json.loads(merged_object_components)

    # Verify vertex counts of original object to ensure merged object metadata being up to date
    for obj_name, vertex_count in vertex_counts.items():
        obj = get_object(obj_name)
        if len(obj.data.vertices) != vertex_count:
            raise ValueError(f'Object `{obj_name}` vertex count {len(obj.data.vertices)} differs from {vertex_count} recorded to `{merged_obj.name}`!')

    # Ensure merged object being in OBJECT mode and read per-vertex coords either from mesh.vertices or basis shapekey
    with OpenObject(context, merged_obj, 'OBJECT') as obj:
        if obj.data.shape_keys is None or len(getattr(obj.data.shape_keys, 'key_blocks', [])) == 0:
            # Merged object has no shapekeys, fetch data from mesh
            mesh = obj.evaluated_get(context.evaluated_depsgraph_get()).to_mesh()
            position_data = numpy.empty(len(mesh.vertices), dtype=(numpy.float32, 3))
            mesh.vertices.foreach_get('undeformed_co', position_data.ravel())
        else:
            # Merged object has shapekeys, fetch data from Basis shapekey
            key_block = obj.data.shape_keys.key_blocks['Basis']
            position_data = numpy.empty(len(key_block.data), dtype=(numpy.float32, 3))
            key_block.data.foreach_get('co', position_data.ravel())

    offset = 0
    for obj_name, vertex_count in vertex_counts.items():
        # Ensure target object being in OBJECT mode and write per-vertex coords either to mesh.vertices or basis shapekey
        with OpenObject(context, obj_name, 'OBJECT') as obj:
            if obj.data.shape_keys is None or len(getattr(obj.data.shape_keys, 'key_blocks', [])) == 0:
                # Target object has no shapekeys, write data to mesh
                obj.data.vertices.foreach_set('co', position_data[offset:(offset+vertex_count)].ravel())
            else:
                # Target object has shapekeys, write data to Basis shapekey
                key_block = obj.data.shape_keys.key_blocks['Basis']
                # Apply sculpt to shapekeys
                if apply_deltas_to_shapekeys:
                    # Get vertex positions from Basis shapekey of original object
                    original_position_data = numpy.empty(len(key_block.data), dtype=(numpy.float32, 3))
                    key_block.data.foreach_get('co', original_position_data.ravel())
                    # Calculate vertex position deltas
                    position_data_diff = original_position_data - position_data[offset:(offset+vertex_count)]
                    # Apply position deltas to shapekeys
                    shapekey_position_data = numpy.empty(len(key_block.data), dtype=(numpy.float32, 3))
                    for key in obj.data.shape_keys.key_blocks:
                        if key.name == 'Basis':
                            continue
                        key.data.foreach_get('co', shapekey_position_data.ravel())
                        shapekey_position_data -= position_data_diff
                        key.data.foreach_set("co", shapekey_position_data.ravel())
                # Apply sculpt to Basis shapekey
                key_block.data.foreach_set("co", position_data[offset:(offset+vertex_count)].ravel())
            # Apply updated data to mesh
            obj.data.update()
        offset += vertex_count


def convert_vertex_colors_storage_format(context):

    for selected_obj in context.selected_objects:

        with OpenObject(context, selected_obj, 'OBJECT') as obj:

            mesh = obj.evaluated_get(context.evaluated_depsgraph_get()).to_mesh()

            if not hasattr(mesh, 'vertex_colors'):
                continue

            for semantic_name in ['COLOR', 'COLOR1']:

                if semantic_name not in mesh.vertex_colors:
                    if semantic_name in mesh.color_attributes:
                        print(f"[{obj.name}]: Color layer `{semantic_name}` is already stored as Linear")
                    else:
                        print(f"[{obj.name}]: Color layer `{semantic_name}` not found in the object")
                    continue

                # Allocate intermediate data array
                data = numpy.empty(len(mesh.loops), dtype=(numpy.float32, 4))
                # Fetch data from deprecated color layer
                vertex_color = mesh.vertex_colors[semantic_name]
                vertex_color.data.foreach_get('color', data.ravel())
                # Remove deprecated color layer
                obj.data.vertex_colors.remove(vertex_color)
                # Write data to the new color layer
                color_attribute = obj.data.color_attributes.new(name=semantic_name, type='FLOAT_COLOR', domain='CORNER')
                color_attribute.data.foreach_set('color', data.flatten())

                print(f"[{obj.name}]: Converted legacy color layer `{semantic_name}` to Linear")

            obj.data.update()
