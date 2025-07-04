import bpy

from bpy.props import BoolProperty, StringProperty, PointerProperty, IntProperty, FloatProperty, CollectionProperty

from ...exceptions import clear_error, ConfigError

    
from ....migoto_io.blender_tools.vertex_groups import *
from ....migoto_io.blender_tools.modifiers import *
from ....migoto_io.blender_tools.meshes import *


class WWMI_MergeVertexGroups(bpy.types.Operator):
    bl_idname = "wwmi_tools.merge_vertex_groups"
    bl_label = "合并具有相同名称的顶点组"
    bl_description = "将名称中点 (.) 之前部分相同的顶点组进行合并 (例如: 将 7 与 7.1 和 7.3 合并). 由 SilentNightSound#7430 提供"
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
    bl_label = "填充数字顶点组的空隙"
    bl_description = "为选定对象添加缺失的顶点组, 并对其顶点组列表进行排序 (例如: 如果对象有 0、4、2 组顶点组, 它将添加缺失的 1 和 3, 并将列表排序为 0、1、2、3、4). 由 SilentNightSound#7430 提供"
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
    bl_label = "移除未使用的空顶点组"
    bl_description = "从选定对象中移除权重为零的顶点组. 由 Ave 提供"
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
    bl_label = "移除全部顶点组"
    bl_description = "从选定对象中移除全部顶点组"
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
    bl_label = "为具有形态键的对象应用修改器"
    bl_description = "为具有形态键的对象应用选定的修改器, 并从堆栈中移除 (解决了在'对象修改器'中点击'应用'按钮时出现的'无法将修改器应用于具有形状键的网格'错误). 由Przemysław Bągard提供"
    bl_options = {'REGISTER', 'UNDO'}

    def item_list(self, context):
        return [(modifier.name, modifier.name, modifier.name) for modifier in bpy.context.object.modifiers]
    
    my_collection: CollectionProperty(
        type=PropertyCollectionModifierItem
    ) # type: ignore
    
    disable_armatures: BoolProperty(
        name="不包括骨架变形",
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
    bl_label = "创建合并对象 (至少选择两个对象以上)"
    bl_description = "将选定对象合并为一个对象以便进行雕刻. 警告: 在完成合并对象的雕刻工作之前，请不要在原始对象中添加或删除顶点!"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            create_merged_object(context)
            
        except ValueError as e:
            self.report({'ERROR'}, str(e))
            
        return {'FINISHED'}
    

class WWMI_ApplyMergedObjectSculpt(bpy.types.Operator):
    bl_idname = "wwmi_tools.apply_merged_object_sculpt"
    bl_label = "应用合并对象的顶点位置变换"
    bl_description = "将合并对象的顶点位置传输回原始对象"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            transfer_position_data(context)
            
        except ValueError as e:
            self.report({'ERROR'}, str(e))
            
        return {'FINISHED'}
    