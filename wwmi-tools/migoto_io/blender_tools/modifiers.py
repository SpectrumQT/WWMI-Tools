import time
import re
import numpy

import bpy


def apply_modifiers_for_object_with_shape_keys(
    context: bpy.types.Context,
    selected_modifiers: list[str] | None = None,
    disable_armatures: bool = False,
    persistent_shapekey_name_pattern: re.Pattern | None = None,
):
    start_time = time.time()
    
    view_layer = context.view_layer
    obj = view_layer.objects.active
    depsgraph = context.evaluated_depsgraph_get()

    if obj.type != 'MESH':
        return (False, "Active object must be a mesh")

    # Object has no modifiers.
    if len(obj.modifiers) == 0:
        # Do nothing (no modifiers to apply).
        return (True, None)
    
    # Modifier selection logic.
    if selected_modifiers is None:
        apply_all_visible_modifiers = True
    else:
        apply_all_visible_modifiers = False

    # Selected modifiers list is provided, but empty.
    if not apply_all_visible_modifiers and not selected_modifiers:
        # Do nothing (no selected modifiers to apply).
        return (True, None)

    # Remember all disabled modifiers to re-enable them once run is complete.
    disabled_modifiers = set()

    # Disable all modifiers that aren't selected.
    if selected_modifiers:
        for modifier in obj.modifiers:
            if modifier.name in selected_modifiers or not modifier.show_viewport:
                continue
            modifier.show_viewport = False
            disabled_modifiers.add(modifier)

    # Disable armature modifiers if requested.
    if disable_armatures:
        for modifier in obj.modifiers:
            if modifier.type != 'ARMATURE' or not modifier.show_viewport:
                continue
            if selected_modifiers and modifier.name in selected_modifiers:
                continue
            modifier.show_viewport = False
            disabled_modifiers.add(modifier)

    try:

        # If there are no shape keys, just apply selected modifiers.
        if not obj.data.shape_keys:

            if apply_all_visible_modifiers:
                # Apply all enabled modifiers using built-in "Visible Geometry To Mesh".
                bpy.ops.object.convert(target='MESH')
                print(f"Applied all visible modifiers to object without shapekeys: {time.time() - start_time:.3f}s ({obj.name})")
            else:
                # Apply only selected modifiers.
                for mod in obj.modifiers:
                    if mod.name in selected_modifiers:
                        bpy.ops.object.modifier_apply(modifier=mod.name)
                print(f"Applied selected modifiers ({len(selected_modifiers)} total) to object without shapekeys: {time.time() - start_time:.3f}s ({obj.name})")

            return (True, None)

        key_blocks = obj.data.shape_keys.key_blocks
        shapekeys_count = len(key_blocks)

        # Fast path for cases when all modifiers are to be applied and only shapekeys with known name pattern must be preserved.
        # If there are no shapekeys matching provided pattern, we can just collapse visible geometry to mesh.
        if apply_all_visible_modifiers and persistent_shapekey_name_pattern:
            if not any(persistent_shapekey_name_pattern.search(k.name.lower()) for k in key_blocks):
                # Apply all enabled modifiers using built-in "Visible Geometry To Mesh".
                bpy.ops.object.convert(target='MESH')
                print(f"Applied all visible modifiers to object without persistent shapekeys: {time.time() - start_time:.3f}s ({obj.name})")

                return (True, None)

        # Store metadata.
        properties = [{
            "name": k.name,
            "mute": k.mute,
            "interpolation": k.interpolation,
            "relative_key": k.relative_key.name if k.relative_key else None,
            "slider_max": k.slider_max,
            "slider_min": k.slider_min,
            "value": k.value,
            "vertex_group": k.vertex_group
        } for k in key_blocks]

        # Create temp object for baking.
        temp_obj = obj.copy()
        temp_obj.data = obj.data.copy()
        context.collection.objects.link(temp_obj)

        temp_keys = temp_obj.data.shape_keys.key_blocks

        baked_meshes = []
        vertex_count = None

        # Bake each shapekey via depsgraph.
        prev_shapekey = None

        for i, key in enumerate(temp_keys):
            # Isolate shapekey.
            key.value = 1.0
            if prev_shapekey:
                prev_shapekey.value = 0.0

            view_layer.update()

            eval_obj = temp_obj.evaluated_get(depsgraph)

            mesh = bpy.data.meshes.new_from_object(eval_obj)

            if vertex_count is None:
                vertex_count = len(mesh.vertices)
            elif len(mesh.vertices) != vertex_count:
                bpy.data.objects.remove(temp_obj, do_unlink=True)
                    
                return (False, "Modifiers changed topology (vertex mismatch)")

            baked_meshes.append(mesh)
            
            prev_shapekey = key

        if prev_shapekey:
            prev_shapekey.value = 0.0

        # Cleanup temp object.
        bpy.data.objects.remove(temp_obj, do_unlink=True)

        # Apply Basis shapekeys.
        obj.shape_key_clear()

        old_mesh = obj.data
        obj.data = baked_meshes[0].copy()
        bpy.data.meshes.remove(old_mesh)

        obj.shape_key_add(name="Basis", from_mix=False)

        vert_count = len(obj.data.vertices)
        buffer = numpy.empty(vert_count * 3, dtype=numpy.float32)

        # Add other shapekeys.
        for i in range(1, shapekeys_count):
            mesh = baked_meshes[i]

            shape_key = obj.shape_key_add(name=f"TEMP_{i}", from_mix=False)

            mesh.vertices.foreach_get("co", buffer)
            shape_key.data.foreach_set("co", buffer)

        # Restore shapekeys metadata.
        keys = obj.data.shape_keys.key_blocks

        for i in range(shapekeys_count):
            keys[i].name = properties[i]["name"]

        for i in range(shapekeys_count):
            key = keys[i]
            meta = properties[i]

            key.mute = meta["mute"]
            key.interpolation = meta["interpolation"]
            key.slider_max = meta["slider_max"]
            key.slider_min = meta["slider_min"]
            key.value = meta["value"]
            key.vertex_group = meta["vertex_group"]

            rel = meta["relative_key"]
            if rel:
                for k in keys:
                    if k.name == rel:
                        key.relative_key = k
                        break

        # Cleanup meshes.
        for mesh in baked_meshes:
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh)

        if apply_all_visible_modifiers:
            print(f"Applied all visible modifiers to object with {shapekeys_count} shapekeys: {time.time() - start_time:.3f}s ({obj.name})")
        else:
            print(f"Applied selected modifiers ({len(selected_modifiers)} total) to object with {shapekeys_count} shapekeys: {time.time() - start_time:.3f}s ({obj.name})")

        return (True, None)
    
    finally:
        # Re-enable disabled modifiers
        for modifier in disabled_modifiers:
            modifier.show_viewport = True
