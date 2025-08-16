import subprocess
import bpy

from textwrap import dedent


from bpy.props import BoolProperty, StringProperty, PointerProperty, IntProperty, FloatProperty, CollectionProperty

from .. import bl_info
from .. import addon_updater_ops

from .exceptions import clear_error, ConfigError

from ..migoto_io.blender_interface.objects import *
from ..migoto_io.blender_interface.collections import *
from ..migoto_io.blender_interface.utility import *

from ..blender_import.blender_import import blender_import
from ..blender_export.blender_export import blender_export
from ..blender_export.ini_maker import IniMaker
from ..extract_frame_data.extract_frame_data import extract_frame_data

from .modules.toolbox.ui import *


def add_row_with_error_handler(layout, cfg, setting_names):
    if not cfg.last_error_setting_name or cfg.last_error_setting_name not in setting_names:
        return layout.row()
    else:
        layout.alert = True
        row = layout.row()
        error_lines = cfg.last_error_text.split('\n')
        
        if len(error_lines) == 1:
            error_row = layout.row()
            error_row.alignment = 'CENTER'
            error_row.label(text=error_lines[0], icon='ERROR')
        else:
            error_box = layout.box()
            error_box.label(text=error_lines[0], icon='ERROR')
            for line in error_lines[1:]:
                if not line.strip():
                    continue
                error_box.label(text=line, icon='BLANK1') 
        layout.alert = False
        return row


class WWMI_TOOLS_PT_SIDEBAR(bpy.types.Panel):
    """
    Wuthering Waves modding toolkit
    """

    bl_idname = "WWMI_TOOLS_PT_SIDEBAR"
    bl_label = "WWMI Tools"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "WWMI Tools"
    # bl_context = "objectmode"

    # @classmethod
    # def poll(cls, context):
    #     return (context.object is not None)

    def draw_header(self, context):
        layout = self.layout
        row = layout.row()
        row.alignment = 'RIGHT'
        row.label(text="v"+".".join(str(i) for i in bl_info.get('version', (0, 0, 0))))

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        cfg = context.scene.wwmi_tools_settings
        layout = self.layout

        layout.row().prop(cfg, 'tool_mode')

        if cfg.tool_mode == 'TOOLS_MODE':
            self.draw_menu_tools_mode(context)

        if cfg.tool_mode == 'EXPORT_MOD':
            self.draw_menu_export_mod(context)

        elif cfg.tool_mode == 'IMPORT_OBJECT':
            self.draw_menu_import_object(context)

        elif cfg.tool_mode == 'EXTRACT_FRAME_DATA':
            self.draw_menu_extract_frame_data(context)

    def draw_menu_tools_mode(self, context):
        cfg = context.scene.wwmi_tools_settings
        layout = self.layout

        layout.row().operator(WWMI_ApplyModifierForObjectWithShapeKeysOperator.bl_idname)
        layout.row().operator(WWMI_MergeVertexGroups.bl_idname)
        layout.row().operator(WWMI_FillGapsInVertexGroups.bl_idname)
        layout.row().operator(WWMI_RemoveUnusedVertexGroups.bl_idname)
        layout.row().operator(WWMI_RemoveAllVertexGroups.bl_idname)
        layout.row().operator(WWMI_CreateMergedObject.bl_idname)
        layout.row().operator(WWMI_ApplyMergedObjectSculpt.bl_idname)

    def draw_menu_export_mod(self, context):
        cfg = context.scene.wwmi_tools_settings
        layout = self.layout
        
        layout.row()
        
        row = add_row_with_error_handler(layout, cfg, 'component_collection')
        row.prop(cfg, 'component_collection')

        row = add_row_with_error_handler(layout, cfg, 'object_source_folder')
        row.prop(cfg, 'object_source_folder')

        row = add_row_with_error_handler(layout, cfg, 'mod_output_folder')
        row.prop(cfg, 'mod_output_folder')
        
        layout.row().prop(cfg, 'mod_skeleton_type')

        layout.row()
        
        layout.row().prop(cfg, 'partial_export')

        if not cfg.partial_export:
            layout.row()

            layout.row().prop(cfg, 'mirror_mesh')
            
            if bpy.app.version >= (3, 5):
                row = layout.row()
                row.prop(cfg, 'ignore_nested_collections')
                if not cfg.ignore_nested_collections:
                    row.prop(cfg, 'ignore_hidden_collections')
                
            layout.row().prop(cfg, 'ignore_hidden_objects')
            layout.row().prop(cfg, 'ignore_muted_shape_keys')

            layout.row()
            
            layout.row().prop(cfg, 'apply_all_modifiers')
            layout.row().prop(cfg, 'copy_textures')

            col = layout.column(align=True)
            grid = col.grid_flow(columns=2, align=True)
            grid.alignment = 'LEFT'
            grid.prop(cfg, 'write_ini')
            if cfg.write_ini:
                grid.prop(cfg, 'comment_ini')

                if cfg.mod_skeleton_type == 'MERGED':
                    layout.row().prop(cfg, 'skeleton_scale')
                layout.row().prop(cfg, 'unrestricted_custom_shape_keys')

    def draw_menu_import_object(self, context):
        cfg = context.scene.wwmi_tools_settings
        layout = self.layout
        
        layout.row()

        row = add_row_with_error_handler(layout, cfg, 'object_source_folder')
        row.prop(cfg, 'object_source_folder')

        layout.row().prop(cfg, 'import_skeleton_type')
        layout.row().prop(cfg, 'mirror_mesh')

        layout.row()

        layout.row().operator(WWMI_Import.bl_idname)

    def draw_menu_extract_frame_data(self, context):
        cfg = context.scene.wwmi_tools_settings
        layout = self.layout
        
        layout.row()

        row = add_row_with_error_handler(layout, cfg, 'frame_dump_folder')
        row.prop(cfg, 'frame_dump_folder')

        layout.row().prop(cfg, 'extract_output_folder')

        layout.row()

        col = layout.column(align=True)
        grid = col.grid_flow(columns=2, align=True)
        grid.alignment = 'LEFT'
        grid.prop(cfg, 'skip_small_textures')
        if cfg.skip_small_textures:
            grid.prop(cfg, 'skip_small_textures_size')

        layout.row().prop(cfg, 'skip_jpg_textures')
        layout.row().prop(cfg, 'skip_same_slot_hash_textures')

        layout.row()

        layout.row().operator(WWMI_ExtractFrameData.bl_idname)


class WWMI_TOOLS_PT_SidePanelPartialExport(bpy.types.Panel):
    bl_label = "Partial Export"
    bl_parent_id = "WWMI_TOOLS_PT_SIDEBAR"
    # bl_options = {'DEFAULT_CLOSED'}
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "WWMI Tools"
    bl_options = {'HIDE_HEADER'}
    bl_idname = 'wwmi_1'
    bl_order = 1

    @classmethod
    def poll(cls, context):
        cfg = context.scene.wwmi_tools_settings
        return cfg.tool_mode == 'EXPORT_MOD' and cfg.partial_export

    def draw(self, context):
        layout = self.layout
        cfg = context.scene.wwmi_tools_settings
        box = layout.box()
        box.row().prop(cfg, 'export_index')
        box.row().prop(cfg, 'export_positions')
        box.row().prop(cfg, 'export_blends')
        box.row().prop(cfg, 'export_vectors')
        box.row().prop(cfg, 'export_colors')
        box.row().prop(cfg, 'export_texcoords')
        box.row().prop(cfg, 'export_shapekeys')


class WWMI_TOOLS_PT_SidePanelModInfo(bpy.types.Panel):
    bl_label = "模组信息"
    bl_parent_id = "WWMI_TOOLS_PT_SIDEBAR"
    # bl_options = {'DEFAULT_CLOSED'}
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "WWMI Tools"
    bl_order = 13

    @classmethod
    def poll(cls, context):
        cfg = context.scene.wwmi_tools_settings
        return cfg.tool_mode == 'EXPORT_MOD' and not cfg.partial_export

    def draw(self, context):
        layout = self.layout
        cfg = context.scene.wwmi_tools_settings
        layout.row().prop(cfg, 'mod_name')
        layout.row().prop(cfg, 'mod_author')
        layout.row().prop(cfg, 'mod_desc')
        layout.row().prop(cfg, 'mod_link')
        layout.row().prop(cfg, 'mod_logo')


class WWMI_TOOLS_PT_SidePanelIniTemplate(bpy.types.Panel):
    bl_label = "INI 模版"
    bl_idname = "WWMI_TOOLS_PT_INI_TEMPLATE"
    bl_parent_id = "WWMI_TOOLS_PT_SIDEBAR"
    bl_options = {'DEFAULT_CLOSED'}
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "WWMI Tools"
    bl_order = 80

    @classmethod
    def poll(cls, context):
        cfg = context.scene.wwmi_tools_settings
        return cfg.tool_mode == 'EXPORT_MOD' and not cfg.partial_export
    
    def draw(self, context):
        layout = self.layout
        cfg = context.scene.wwmi_tools_settings
    
        row = add_row_with_error_handler(layout, cfg, ['use_custom_template', 'custom_template_source'])

        split = row.split(factor=0.5)

        col_left = split.column()
        col_left.prop(cfg, 'use_custom_template')

        col_left = split.column()
        col_left.prop(cfg, 'custom_template_source')
        
        if cfg.custom_template_source == 'INTERNAL':
            layout.row().operator(WWMI_OpenIniTemplateEditor.bl_idname)

        elif cfg.custom_template_source == 'EXTERNAL':
            row = add_row_with_error_handler(layout, cfg, 'custom_template_path')
            row.prop(cfg, 'custom_template_path')

            row = layout.row()
            split = row.split(factor=0.5)

            col_left = split.column()
            col_left.operator(WWMI_OpenIniTemplateEditor.bl_idname)
            
            col_right = split.column()
            if cfg.custom_template_live_update:
                col_right.operator(WWMI_IniTemplateEditor_ToggleLiveUpdates.bl_idname, text="停止 INI 更新")
            else:
                col_right.operator(WWMI_IniTemplateEditor_ToggleLiveUpdates.bl_idname, text="启动 INI 更新")


class WWMI_TOOLS_PT_SidePanelExportFooter(bpy.types.Panel):
    bl_label = "Export"
    bl_parent_id = "WWMI_TOOLS_PT_SIDEBAR"
    # bl_options = {'DEFAULT_CLOSED'}
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "WWMI Tools"
    bl_options = {'HIDE_HEADER'}
    bl_order = 99

    @classmethod
    def poll(cls, context):
        cfg = context.scene.wwmi_tools_settings
        return cfg.tool_mode == 'EXPORT_MOD'
    
    def draw(self, context):
        layout = self.layout
        cfg = context.scene.wwmi_tools_settings
        if cfg.custom_template_live_update:
            layout.operator(WWMI_IniTemplateEditor_ToggleLiveUpdates.bl_idname, text="Stop Ini Updates")
        else:
            layout.row().operator(WWMI_Export.bl_idname)


# @orientation_helper(axis_forward='-Z', axis_up='Y')
class WWMI_Import(bpy.types.Operator):
    """
    Import object extracted from frame dump data with WWMI
    """
    bl_idname = "wwmi_tools.import_object"
    bl_label = "导入对象"
    bl_description = "从帧转储数据中导入使用 WWMI 提取的对象"

    bl_options = {'UNDO'}

    def execute(self, context):
        try:
            cfg = context.scene.wwmi_tools_settings

            clear_error(cfg)

            cfg.mod_skeleton_type = cfg.import_skeleton_type
            
            blender_import(self, context, cfg)

        except ConfigError as e:
            self.report({'ERROR'}, str(e))
        
        return {'FINISHED'}


class WWMI_Export(bpy.types.Operator):
    """
    Export object as WWMI mod
    """
    bl_idname = "wwmi_tools.export_mod"
    bl_label = "导出模组"
    bl_description = "将对象导出为 WWMI 模组"

    def get_excluded_buffers(self, context):
        """
        Calculates list of exported buffers and processed semantics based on partial export settings
        Speeds up export of single buffer up to 5 times compared to full export
        """
        cfg = context.scene.wwmi_tools_settings

        if cfg.partial_export:
            # Loop data is used to create list of exported vertices, so there are only two options for partial export:
            # 1. Recalculate each time whenever Index / Vector / Color / TexCoord buffers is selected
            # 2. Load from cache if there is no Index / Vector / Color / TexCoord buffers selected
            exclude_buffers = []

            if not cfg.export_index:
                exclude_buffers.append('Index')
            if not cfg.export_positions:
                exclude_buffers.append('Position')
            if not cfg.export_blends:
                exclude_buffers.append('Blend')
            if not cfg.export_vectors:
                exclude_buffers.append('Vector')
            if not cfg.export_colors:
                exclude_buffers.append('Color')
            if not cfg.export_texcoords:
                exclude_buffers.append('TexCoord')
            if not cfg.export_shapekeys:
                exclude_buffers.append('ShapeKeyOffset')
                exclude_buffers.append('ShapeKeyVertexId')
                exclude_buffers.append('ShapeKeyVertexOffset')
                
            return exclude_buffers
    
        else:

            return []

    def execute(self, context):
        try:
            cfg = context.scene.wwmi_tools_settings

            clear_error(cfg)

            excluded_buffers = self.get_excluded_buffers(context)

            blender_export(self, context, cfg, excluded_buffers)
            
        except ConfigError as e:
            self.report({'ERROR'}, str(e))
            
        return {'FINISHED'}


class WWMI_ExtractFrameData(bpy.types.Operator):
    """
    Extract objects from frame dump
    """
    bl_idname = "wwmi_tools.extract_frame_data"
    bl_label = "从帧转储中提取对象"
    bl_description = "从帧转储中提取对象"

    def execute(self, context):
        try:
            cfg = context.scene.wwmi_tools_settings

            clear_error(cfg)

            output = extract_frame_data(cfg)
            
            objects_missing_shapekeys = []
            for object_hash, object_data in output.objects.items():
                if object_data.shapekeys.offsets_hash and not object_data.shapekeys.shapekey_offsets:
                    objects_missing_shapekeys.append(object_hash)
            if len(objects_missing_shapekeys) > 0:
                self.report({'WARNING'}, dedent(f"""
                    Objects {', '.join(objects_missing_shapekeys)} were skipped:
                    Frame dump is missing shapekeys data!
                    Try to make another dump with ongoing facial animation.
                """).strip())
            
        except ConfigError as e:
            self.report({'ERROR'}, str(e))
            
        return {'FINISHED'}


class WWMI_OpenIniTemplateEditor(bpy.types.Operator):
    """
    Open current custom template in internal or external editor.
    """
    bl_idname = "wwmi_tools.open_ini_template_editor"
    bl_label = "编辑模版"
    bl_description = "Open current custom template file in internal or external editor."

    def execute(self, context):
        cfg = context.scene.wwmi_tools_settings

        if cfg.custom_template_source == 'EXTERNAL':
            template_path = resolve_path(cfg.custom_template_path)
            if not template_path.is_file():
                raise ValueError(f'未找到自定义 ini 模板文件: `{template_path}`!')
            subprocess.Popen([f'{str(template_path)}'], shell=True)
            return {'FINISHED'}

        text_name = "CustomIniTemplate"

        if text_name in bpy.data.texts:
            text = bpy.data.texts[text_name]
        else:
            text = bpy.data.texts.new(text_name)
        
        if not text.as_string().strip():
            text.clear()
            text.write(IniMaker.get_default_template(context, cfg, remove_code_comments=True))
            text.cursor_set(0)

        new_window = bpy.ops.wm.window_new()
        
        new_window_context = bpy.context.window_manager.windows[-1]

        # Switch the area to TEXT_EDITOR and assign the text
        for area in new_window_context.screen.areas:
            area.type = 'TEXT_EDITOR'
            text_area = area
            for space in area.spaces:
                if space.type == 'TEXT_EDITOR':
                    space.text = text

        # Toggle Tools sidebar
        if text_area:
            for region in text_area.regions:
                if region.type == 'UI':
                    bpy.ops.wm.context_toggle(data_path="space_data.show_region_ui")
                    break
        
        return {'FINISHED'}


class WWMI_IniTemplateEditor_ToggleLiveUpdates(bpy.types.Operator):
    bl_idname = "wwmi_tools.ini_template_start_live_updates"
    bl_label = "启动 INI 更新"
    bl_description = "一旦启动，WWMI Tools 将使用当前设置运行导出, 并在每次模板编辑时开始写入 mod.ini.\n"
    "Warning! Mod export will be blocked until live updates are stopped!"

    def execute(self, context):
        cfg = context.scene.wwmi_tools_settings
        if cfg.custom_template_live_update:
            cfg.custom_template_live_update = False
        else:
            cfg.custom_template_live_update = True
            bpy.ops.wwmi_tools.export_mod()
        return {'FINISHED'}
    
    @classmethod
    def poll(cls, context):
        cfg = context.scene.wwmi_tools_settings
        return cfg.use_custom_template


class WWMI_IniTemplateEditor_Reset(bpy.types.Operator):
    bl_idname = "wwmi_tools.ini_template_editor_reset"
    bl_label = "重置模版"
    bl_description = "警告! 此操作将重置自定义模板为默认值!"

    def execute(self, context):
        cfg = context.scene.wwmi_tools_settings
        
        text_name = "CustomIniTemplate"

        if text_name in bpy.data.texts:
            text = bpy.data.texts[text_name]
        else:
            text = bpy.data.texts.new(text_name)
        
        text.clear()
        text.write(IniMaker.get_default_template(context, cfg, remove_code_comments=True))
        text.cursor_set(0)

        return {'FINISHED'}
    
    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)
    

class WWMI_TOOLS_PT_TEXT_EDITOR_IniTemplate(bpy.types.Panel):
    bl_label = "INI 模版 - WWMI Tools"
    bl_space_type = "TEXT_EDITOR"
    bl_region_type = "UI"
    bl_category = "Text"

    def draw(self, context):
        layout = self.layout
        cfg = context.scene.wwmi_tools_settings
        
        if cfg.custom_template_live_update:
            layout.operator(WWMI_IniTemplateEditor_ToggleLiveUpdates.bl_idname, text="停止 INI 更新")
        else:
            layout.operator(WWMI_IniTemplateEditor_ToggleLiveUpdates.bl_idname, text="启动 INI 更新")

        layout.operator(WWMI_IniTemplateEditor_Reset.bl_idname)


class UpdaterPanel(bpy.types.Panel):
    """Update Panel"""
    bl_label = "更新设置"
    bl_idname = "WWMI_TOOLS_PT_UpdaterPanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    # bl_context = "objectmode"
    bl_category = "WWMI Tools"
    bl_order = 99
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout

        # Call to check for update in background.
        # Note: built-in checks ensure it runs at most once, and will run in
        # the background thread, not blocking or hanging blender.
        # Internally also checks to see if auto-check enabled and if the time
        # interval has passed.
        addon_updater_ops.check_for_update_background()
        col = layout.column()
        col.scale_y = 0.7
        # Could also use your own custom drawing based on shared variables.
        if addon_updater_ops.updater.update_ready:
            layout.label(text="There's a new update available!", icon="INFO")

        # Call built-in function with draw code/checks.
        addon_updater_ops.update_notice_box_ui(self, context)
        addon_updater_ops.update_settings_ui(self, context)


class DebugPanel(bpy.types.Panel):
    """Debug Panel"""
    bl_label = "调试设置"
    bl_idname = "WWMI_TOOLS_PT_DebugPanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    # bl_context = "objectmode"
    bl_category = "WWMI Tools"
    bl_order = 80
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        cfg = context.scene.wwmi_tools_settings

        layout.row().prop(cfg, 'allow_missing_shapekeys')
        layout.row().prop(cfg, 'remove_temp_object')
        layout.row().prop(cfg, 'export_on_reload')