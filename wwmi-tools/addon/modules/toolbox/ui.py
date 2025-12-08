import bpy

from bpy.props import BoolProperty, StringProperty, PointerProperty, IntProperty, FloatProperty, CollectionProperty

from ...exceptions import clear_error, ConfigError

    
from ....migoto_io.blender_tools.vertex_groups import *
from ....migoto_io.blender_tools.modifiers import *
from ....migoto_io.blender_tools.meshes import *


class WWMI_MergeVertexGroups(bpy.types.Operator):
    bl_idname = "wwmi_tools.merge_vertex_groups"
    bl_label = "Merge Vertex Groups"
    bl_description = "Merges vertex groups with same name before dot (i.e. `7` with `7.1` and `7.3`). Sourced by SilentNightSound#7430"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            for obj in get_selected_objects(context):
                merge_vertex_groups(context, obj)
            
        except ValueError as e:
            self.report({'ERROR'}, str(e))
            
        return {'FINISHED'}
    

class WWMI_FillGapsInVertexGroups(bpy.types.Operator):
    """
    Fills in missing vertex groups for a model so there are no gaps, and sorts to make sure everything is in order
    Works on the currently selected object
    e.g. if the selected model has groups 0 1 4 5 7 2 it adds an empty group for 3 and 6 and sorts to make it 0 1 2 3 4 5 6 7
    Very useful to make sure there are no gaps or out-of-order vertex groups
    """
    bl_idname = "wwmi_tools.fill_gaps_in_vertex_groups"
    bl_label = "Fill Gaps In Vertex Groups"
    bl_description = "Adds missing vertex groups and sorts the VG lists of selected objects (i.e. if object had 0,4,2 groups, it'll add missing 1,3 and sort the list to 0,1,2,3,4). Sourced by SilentNightSound#7430"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            for obj in get_selected_objects(context):
                fill_gaps_in_vertex_groups(context, obj)
            
        except ValueError as e:
            self.report({'ERROR'}, str(e))
            
        return {'FINISHED'}
    

class WWMI_RemoveUnusedVertexGroups(bpy.types.Operator):
    """
    Remove all vertex groups from selected objects
    """
    bl_idname = "wwmi_tools.remove_unused_vertex_groups"
    bl_label = "Remove Unused Vertex Groups"
    bl_description = "Remove vertex groups with zero weights from selected objects. Sourced by Ave"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            for obj in get_selected_objects(context):
                remove_unused_vertex_groups(context, obj)
            
        except ValueError as e:
            self.report({'ERROR'}, str(e))
            
        return {'FINISHED'}
    

class WWMI_RemoveAllVertexGroups(bpy.types.Operator):
    """
    Remove all vertex groups from selected objects
    """
    bl_idname = "wwmi_tools.remove_all_vertex_groups"
    bl_label = "Remove All Vertex Groups"
    bl_description = "Remove all vertex groups from selected objects"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            for obj in get_selected_objects(context):
                remove_all_vertex_groups(context, obj)
            
        except ValueError as e:
            self.report({'ERROR'}, str(e))
            
        return {'FINISHED'}


class PropertyCollectionModifierItem(bpy.types.PropertyGroup):
    checked: BoolProperty(
        name="", 
        default=False
    ) # type: ignore
bpy.utils.register_class(PropertyCollectionModifierItem)


class WWMI_ApplyModifierForObjectWithShapeKeysOperator(bpy.types.Operator):
    bl_idname = "wwmi_tools.apply_modifier_for_object_with_shape_keys"
    bl_label = "Apply Modifiers For Object With Shape Keys"
    bl_description = "Apply selected modifiers and remove from the stack for object with shape keys (Solves 'Modifier cannot be applied to a mesh with shape keys' error when pushing 'Apply' button in 'Object modifiers'). Sourced by Przemysław Bągard"
    bl_options = {'REGISTER', 'UNDO'}

    def item_list(self, context):
        return [(modifier.name, modifier.name, modifier.name) for modifier in bpy.context.object.modifiers]
    
    my_collection: CollectionProperty(
        type=PropertyCollectionModifierItem
    ) # type: ignore
    
    disable_armatures: BoolProperty(
        name="Don't include armature deformations",
        default=True,
    ) # type: ignore
 
    def execute(self, context):
        ob = bpy.context.object
        bpy.ops.object.select_all(action='DESELECT')
        context.view_layer.objects.active = ob
        ob.select_set(True)
        
        selectedModifiers = [o.name for o in self.my_collection if o.checked]
        
        if not selectedModifiers:
            self.report({'ERROR'}, 'No modifier selected!')
            return {'FINISHED'}
        
        success, errorInfo = apply_modifiers_for_object_with_shape_keys(context, selectedModifiers, self.disable_armatures)
        
        if not success:
            self.report({'ERROR'}, errorInfo)
        
        return {'FINISHED'}
        
    def draw(self, context):
        if context.object.data.shape_keys and context.object.data.shape_keys.animation_data:
            self.layout.separator()
            self.layout.label(text="Warning:")
            self.layout.label(text="              Object contains animation data")
            self.layout.label(text="              (like drivers, keyframes etc.)")
            self.layout.label(text="              assigned to shape keys.")
            self.layout.label(text="              Those data will be lost!")
            self.layout.separator()
        #self.layout.prop(self, "my_enum")
        box = self.layout.box()
        for prop in self.my_collection:
            box.prop(prop, "checked", text=prop["name"])
        #box.prop(self, "my_collection")
        self.layout.prop(self, "disable_armatures")
 
    def invoke(self, context, event):
        self.my_collection.clear()
        for i in range(len(bpy.context.object.modifiers)):
            item = self.my_collection.add()
            item.name = bpy.context.object.modifiers[i].name
            item.checked = False
        return context.window_manager.invoke_props_dialog(self)
    

class WWMI_CreateMergedObject(bpy.types.Operator):
    bl_idname = "wwmi_tools.create_merged_object"
    bl_label = "Create Merged Object"
    bl_description = "Join selected objects into merged object for sculpting. WARNING! Do not add or remove vertices in original objects until you done working with the merged one!"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            create_merged_object(context)
            
        except ValueError as e:
            self.report({'ERROR'}, str(e))
            
        return {'FINISHED'}
    

class WWMI_ApplyMergedObjectSculpt(bpy.types.Operator):
    bl_idname = "wwmi_tools.apply_merged_object_sculpt"
    bl_label = "Apply Merged Object Sculpt"
    bl_description = "Transfer vertex positions from merged object to original objects"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            transfer_position_data(context)
            
        except ValueError as e:
            self.report({'ERROR'}, str(e))
            
        return {'FINISHED'}
    

class WWMI_ApplyMergedObjectSculptWithShapekeys(bpy.types.Operator):
    bl_idname = "wwmi_tools.apply_merged_object_sculpt_with_shapekeys"
    bl_label = "Apply Merged Object Sculpt (Shape Keys)"
    bl_description = "Transfer vertex positions from merged object to original objects and apply resulted positions deltas to all shape keys."
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            transfer_position_data(context, apply_deltas_to_shapekeys=True)
            
        except ValueError as e:
            self.report({'ERROR'}, str(e))
            
        return {'FINISHED'}