import bpy
import json

from textwrap import dedent


class WWMI_TOOLS_PT_SidePanelIniToggles(bpy.types.Panel):
    bl_label = "INI 切换"
    bl_idname = "WWMI_TOOLS_PT_INI_TOGGLES"
    bl_parent_id = "WWMI_TOOLS_PT_SIDEBAR"
    bl_options = {'DEFAULT_CLOSED'}
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "WWMI Tools"
    bl_order = 81

    @classmethod
    def poll(cls, context):
        cfg = context.scene.wwmi_tools_settings
        return cfg.tool_mode == 'EXPORT_MOD' and not cfg.partial_export
    
    def draw(self, context):
        layout = self.layout
        cfg = context.scene.wwmi_tools_settings
    
        layout.prop(cfg, 'use_ini_toggles')
        
        layout.operator("wwmi_tools.open_ini_toggles_import_export_editor")

        layout.prop(cfg.ini_toggles, 'hide_empty_states')
        layout.prop(cfg.ini_toggles, 'hide_default_conditions')

        row = layout.row()
        row.operator("wwmi_tools.collapse_toggle_vars", icon="TRIA_DOWN")
        row.operator("wwmi_tools.expand_toggle_vars", icon="TRIA_RIGHT")

        layout.operator("wwmi_tools.add_toggle_var", text="添加变量", icon="ADD")

        for i in reversed(range(len(cfg.ini_toggles.vars))):
            var = cfg.ini_toggles.vars[i]

            box = layout.box()

            row = box.row()

            row.prop(var, "ui_expanded", icon="TRIA_DOWN" if var.ui_expanded else "TRIA_RIGHT", emboss=False, text="")

            hotkeys = " ".join([f"[{binding}]" for binding in var.get_formatted_hotkeys(join_arg='+') if binding])

            if var.ui_expanded:
                split = row.split(factor=0.7)
                split.prop(var, "name", text="")
                split.label(text=hotkeys)
            else:
                row.label(text=f'{var.name} {hotkeys}')

            if var.ui_expanded:
                op = row.operator("wwmi_tools.add_var_state", text="", icon="ADD")
                op.var_index = i

            op = row.operator("wwmi_tools.edit_toggle_var", text="", icon="PREFERENCES")
            op.var_index = i
            if not var.ui_expanded:
                op = row.operator("wwmi_tools.move_toggle_var", icon='TRIA_UP', text="")
                op.var_index = i
                op.direction = 'UP'
                op = row.operator("wwmi_tools.move_toggle_var", icon='TRIA_DOWN', text="")
                op.var_index = i
                op.direction = 'DOWN'
            op = row.operator("wwmi_tools.remove_toggle_var", text="", icon="X")
            op.var_index = i

            if var.ui_expanded:

                for j, state in enumerate(var.states):
                    if state.name == "-1" and cfg.ini_toggles.hide_empty_states and len(state.objects) == 0:
                        continue

                    sub_box = box.box()
                    sub_row = sub_box.row()

                    conditions = []
                    state_error = False
                    error_text = ""

                    for k, obj_item in enumerate(state.objects):

                        if not obj_item.object:
                            state_error = True
                            error_text = f"错误: 对象 {k} 未设置"

                        if obj_item.has_custom_conditions(var.name, state.name):
                            try:
                                conditions.append('if ' + obj_item.format_conditions())
                            except Exception as e:
                                state_error = True
                                conditions.append(f'ERROR: {e}')
                        else:
                            conditions.append('')

                    sub_row.alert = state_error

                    if var.default_state == state.name:
                        sub_row.label(text=f"状态 {state.name} (默认)")
                    else:
                        sub_row.label(text=f"状态 {state.name}")

                    sub_row.alert = False

                    op = sub_row.operator("wwmi_tools.add_var_state_object", text="", icon="ADD")
                    op.var_index = i
                    op.state_index = j
                    
                    op = sub_row.operator("wwmi_tools.move_toggle_var_state", icon='TRIA_UP', text="")
                    op.var_index = i
                    op.state_index = j
                    op.direction = 'UP'
                    op = sub_row.operator("wwmi_tools.move_toggle_var_state", icon='TRIA_DOWN', text="")
                    op.var_index = i
                    op.state_index = j
                    op.direction = 'DOWN'

                    if state.name == "-1":      
                        sub_row = sub_row.row()
                        sub_row.enabled = False 

                    op = sub_row.operator("wwmi_tools.remove_var_state", text="", icon="X")
                    op.var_index = i
                    op.state_index = j

                    if error_text:
                        sub_box.alert = state_error
                        sub_box.row().label(text=error_text)
                        sub_box.alert = False

                    for k, obj_item in enumerate(state.objects):
                        obj_row = sub_box.row()

                        obj_conditions = conditions[k]
                        condition_error = obj_conditions.startswith('ERR')
                        if obj_conditions:
                            obj_row.alert = condition_error
                            obj_row.label(text=obj_conditions)
                            obj_row.alert = False

                        obj_row = sub_box.row()

                        obj_row.prop(obj_item, "object", text="")

                        obj_row.alert = condition_error      
                        op = obj_row.operator("wwmi_tools.edit_var_state_object", text="", icon="PREFERENCES")
                        obj_row.alert = False      
                        op.var_index = i
                        op.state_index = j
                        op.object_index = k
                        
                        op = obj_row.operator("wwmi_tools.remove_var_state_object", text="", icon="X")
                        op.var_index = i
                        op.state_index = j
                        op.object_index = k


class WWMI_TOOLS_OT_CollapseToggleVars(bpy.types.Operator):
    bl_idname = "wwmi_tools.collapse_toggle_vars"
    bl_label = "折叠变量"
    bl_description = "将列表中的所有变量折叠起来 (退出每个变量的编辑模式)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        cfg = context.scene.wwmi_tools_settings
        for var in cfg.ini_toggles.vars:
            var.ui_expanded = False
        return {'FINISHED'}
    

class WWMI_TOOLS_OT_ExpandToggleVars(bpy.types.Operator):
    bl_idname = "wwmi_tools.expand_toggle_vars"
    bl_label = "展开变量"
    bl_description = "将列表中的所有变量展开 (进入每个变量的编辑模式)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        cfg = context.scene.wwmi_tools_settings
        for var in cfg.ini_toggles.vars:
            var.ui_expanded = True
        return {'FINISHED'}


class WWMI_TOOLS_OT_AddToggleVar(bpy.types.Operator):
    bl_idname = "wwmi_tools.add_toggle_var"
    bl_label = "添加切换变量"
    bl_description = "向 INI 切换逻辑中添加新变量， 它将在 mod.ini 中用于控制其状态中列出的对象的可见性"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        cfg = context.scene.wwmi_tools_settings
        cfg.ini_toggles.add_new_var()
        return {'FINISHED'}


class WWMI_TOOLS_OT_RemoveToggleVar(bpy.types.Operator):
    bl_idname = "wwmi_tools.remove_toggle_var"
    bl_label = "移除切换变量"
    bl_description = "从 INI 切换逻辑中移除变量"
    bl_options = {'REGISTER', 'UNDO'}

    var_index: bpy.props.IntProperty()  # type: ignore

    def execute(self, context):
        cfg = context.scene.wwmi_tools_settings
        cfg.ini_toggles.vars.remove(self.var_index)
        return {'FINISHED'}


class WWMI_TOOLS_OT_MoveToggleVar(bpy.types.Operator):
    bl_idname = "wwmi_tools.move_toggle_var"
    bl_label = "移动切换变量"
    bl_description = "在 INI 切换逻辑列表中移动变量"
    bl_options = {'REGISTER', 'UNDO'}
    
    var_index: bpy.props.IntProperty()  # type: ignore
    direction: bpy.props.EnumProperty(items=[('UP', "Up", ""), ('DOWN', "Down", "")])  # type: ignore

    def execute(self, context):
        cfg = context.scene.wwmi_tools_settings

        if self.direction == 'UP':
            new_idx = self.var_index - 1
        else:
            new_idx = self.var_index + 1

        if new_idx < 0 or new_idx >= len(cfg.ini_toggles.vars):
            return {'CANCELLED'}

        cfg.ini_toggles.vars.move(self.var_index, new_idx)
        return {'FINISHED'}



class WWMI_TOOLS_OT_EditToggleVar(bpy.types.Operator):
    bl_idname = "wwmi_tools.edit_toggle_var"
    bl_label = "编辑变量"
    bl_description = "配置变量的快捷键和默认状态"
    bl_options = {'REGISTER', 'UNDO'}

    var_index: bpy.props.IntProperty()  # type: ignore

    def draw(self, context):
        cfg = context.scene.wwmi_tools_settings
        layout = self.layout
        
        layout.label(text="切换变量设置: ")

        var = cfg.ini_toggles.vars[self.var_index]

        box = layout.box()
        
        row = box.row()
        
        split = row.split(factor=0.7)
        
        split.prop(var, "hotkeys")

        op = split.operator("wm.url_open", text="虚拟键码(VK码)", icon='HELP')
        op.url = "https://learn.microsoft.com/en-us/windows/win32/inputdev/virtual-key-codes"

        row = box.row()
        row.prop_search(var, "default_state", var, "states")

        row = box.row()
        row.prop(var, "hide_empty_state")

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=350)

    def execute(self, context):
        return {'FINISHED'}
    

class WWMI_TOOLS_OT_AddToggleVarState(bpy.types.Operator):
    bl_idname = "wwmi_tools.add_var_state"
    bl_label = "添加状态"
    bl_description = "向变量添加新状态, 每个状态可以控制多个对象的可见性"
    bl_options = {'REGISTER', 'UNDO'}

    var_index: bpy.props.IntProperty()  # type: ignore

    def execute(self, context):
        cfg = context.scene.wwmi_tools_settings
        var = cfg.ini_toggles.vars[self.var_index]
        var.add_new_state()
        return {'FINISHED'}


class WWMI_TOOLS_OT_RemoveToggleVarState(bpy.types.Operator):
    bl_idname = "wwmi_tools.remove_var_state"
    bl_label = "移除状态"
    bl_description = "从 INI 切换逻辑变量中移除这个状态"
    bl_options = {'REGISTER', 'UNDO'}

    var_index: bpy.props.IntProperty()  # type: ignore
    state_index: bpy.props.IntProperty()  # type: ignore

    def execute(self, context):
        cfg = context.scene.wwmi_tools_settings
        var = cfg.ini_toggles.vars[self.var_index]
        var.remove_state(self.state_index)
        return {'FINISHED'}


class WWMI_TOOLS_OT_MoveToggleVarState(bpy.types.Operator):
    bl_idname = "wwmi_tools.move_toggle_var_state"
    bl_label = "移动切换变量状态"
    bl_description = "在列表中移动变量状态"
    bl_options = {'REGISTER', 'UNDO'}
    
    var_index: bpy.props.IntProperty()  # type: ignore
    state_index: bpy.props.IntProperty()  # type: ignore
    direction: bpy.props.EnumProperty(items=[('UP', "Up", ""), ('DOWN', "Down", "")])  # type: ignore

    def execute(self, context):
        cfg = context.scene.wwmi_tools_settings
        var = cfg.ini_toggles.vars[self.var_index]

        if self.direction == 'UP':
            new_idx = self.state_index - 1
        else:
            new_idx = self.state_index + 1

        if new_idx < 0 or new_idx >= len(var.states):
            return {'CANCELLED'}

        var.swap_states(self.state_index, new_idx)

        return {'FINISHED'}


class WWMI_TOOLS_OT_AddToggleVarStateObject(bpy.types.Operator):
    bl_idname = "wwmi_tools.add_var_state_object"
    bl_label = "向状态添加对象, 以使其条件性地可见"
    bl_options = {'REGISTER', 'UNDO'}

    var_index: bpy.props.IntProperty()  # type: ignore
    state_index: bpy.props.IntProperty()  # type: ignore

    def execute(self, context):
        cfg = context.scene.wwmi_tools_settings
        var = cfg.ini_toggles.vars[self.var_index]
        state = var.states[self.state_index]
        state.add_new_state_object(var.name)
        return {'FINISHED'}


class WWMI_TOOLS_OT_RemoveToggleVarStateObject(bpy.types.Operator):
    bl_idname = "wwmi_tools.remove_var_state_object"
    bl_label = "移除状态对象"
    bl_description = "从这个状态中移除这个对象"
    bl_options = {'REGISTER', 'UNDO'}

    var_index: bpy.props.IntProperty()  # type: ignore
    state_index: bpy.props.IntProperty()  # type: ignore
    object_index: bpy.props.IntProperty()  # type: ignore

    def execute(self, context):
        cfg = context.scene.wwmi_tools_settings
        group = cfg.ini_toggles.vars[self.var_index]
        state = group.states[self.state_index]
        state.objects.remove(self.object_index)
        return {'FINISHED'}


class WWMI_TOOLS_OT_EditVarStateObject(bpy.types.Operator):
    bl_idname = "wwmi_tools.edit_var_state_object"
    bl_label = "编辑条件"
    bl_description = "打开自定义条件的配置窗口"

    var_index: bpy.props.IntProperty()  # type: ignore
    state_index: bpy.props.IntProperty()  # type: ignore
    object_index: bpy.props.IntProperty()  # type: ignore

    def draw(self, context):
        cfg = context.scene.wwmi_tools_settings
        layout = self.layout
        
        layout.label(text="状态中对象的条件: ")

        var = cfg.ini_toggles.vars[self.var_index]
        state = var.states[self.state_index]
        obj = state.objects[self.object_index]

        for i, condition in enumerate(obj.conditions):
            box = layout.box()
            
            row = box.row()

            split = row.split(factor=0.1)

            split.prop(condition, "logic", text="")
            
            split = split.split(factor=0.2)

            split.prop(condition, "type", text="")

            split = split.split(factor=0.5)

            if condition.type == 'TOGGLE':
                split.prop_search(condition, "var", cfg.ini_toggles, "vars", text="")
            else:
                split.prop(condition, "var", text="")

            split = split.split(factor=0.3)

            split.prop(condition, "operator", text="")
            
            split = split.split(factor=0.8)

            if condition.type == 'TOGGLE':
                cond_group = cfg.ini_toggles.vars.get(condition.var, None)
                if cond_group is not None:
                    split.prop_search(condition, "state", cond_group, "states", text="")
                else:
                    split.alert = True
                    split.label(text="< Select Var! >")
                    split.alert = False
            else:
                split.prop(condition, "state", text="")

            remove_op = split.operator("wwmi_tools.remove_condition", text="", icon='X')
            remove_op.var_index = self.var_index
            remove_op.state_index = self.state_index
            remove_op.object_index = self.object_index
            remove_op.condition_index = i

        add_op = layout.operator("wwmi_tools.add_condition")
        add_op.var_index = self.var_index
        add_op.state_index = self.state_index
        add_op.object_index = self.object_index

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=500)

    def execute(self, context):
        return {'FINISHED'}
    

class WWMI_TOOLS_OT_AddToggleVarStateObjectCondition(bpy.types.Operator):
    bl_idname = "wwmi_tools.add_condition"
    bl_label = "添加条件"
    bl_options = {'REGISTER', 'UNDO'}

    var_index: bpy.props.IntProperty() # type: ignore
    state_index: bpy.props.IntProperty() # type: ignore
    object_index: bpy.props.IntProperty() # type: ignore

    def execute(self, context):
        cfg = context.scene.wwmi_tools_settings
        obj = cfg.ini_toggles.vars[self.var_index].states[self.state_index].objects[self.object_index]
        obj.conditions.add()
        return {'FINISHED'}


class WWMI_TOOLS_OT_RemoveToggleVarStateObjectCondition(bpy.types.Operator):
    bl_idname = "wwmi_tools.remove_condition"
    bl_label = "移除条件"
    bl_options = {'REGISTER', 'UNDO'}

    var_index: bpy.props.IntProperty() # type: ignore
    state_index: bpy.props.IntProperty() # type: ignore
    object_index: bpy.props.IntProperty() # type: ignore
    condition_index: bpy.props.IntProperty() # type: ignore

    def execute(self, context):
        cfg = context.scene.wwmi_tools_settings
        obj = cfg.ini_toggles.vars[self.var_index].states[self.state_index].objects[self.object_index]
        if self.condition_index < len(obj.conditions):
            obj.conditions.remove(self.condition_index)
        return {'FINISHED'}


class WWMI_TOOLS_OpenIniTogglesImportExportEditor(bpy.types.Operator):
    bl_idname = "wwmi_tools.open_ini_toggles_import_export_editor"
    bl_label = "打开 INI 切换逻辑的导入导出"
    bl_description = "打开文本编辑器窗口, 用于导入或导出 INI 切换逻辑变量"

    def execute(self, context):
        cfg = context.scene.wwmi_tools_settings

        text_name = "IniTogglesImportExportText"

        if text_name in bpy.data.texts:
            text = bpy.data.texts[text_name]
        else:
            text = bpy.data.texts.new(text_name)
        
        text.clear()
        text.write(dedent("""
            英文介绍:
            This tool allows to backup your toggles or copy them to another project aka .blend file

            To "[Import]" Ini Toggles Vars:
            1. Create new text via button on the middle panel above (or clear this text)
            2. Paste Ini Toggles export text
            3. Press "Import Ini Toggles" on side panel "Ini Toggles - WWMI Tools" to the right

            To "[Export]" Ini Toggles Vars:
            1. Press "Export Ini Toggles" on side panel "Ini Toggles - WWMI Tools" to the right
            2. Copy generated export text
                          
            中文介绍 (AI翻译不一定准确, 必要时请以英文为准):
            这个工具允许你备份你的切换逻辑, 或者将它们复制到另一个项目 (即 .blend 文件)
            导入 INI 切换变量的步骤:
            1. 通过中间面板上方的按钮创建新文本 (或清除当前文本)
            2. 粘贴 INI 切换导出文本
            3. 点击右侧 "INI 切换 - WWMI Tools" 侧边栏中的 "导入 INI 切换" 按钮
     
            导出 INI 切换变量的步骤:
            1. 点击右侧 "INI 切换 - WWMI Tools" 侧边栏中的 "导出 INI 切换" 按钮
            2. 复制生成的导出文本                      
        """))
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


class WWMI_TOOLS_ExportIniToggles(bpy.types.Operator):
    bl_idname = "wwmi_tools.export_ini_toggles"
    bl_label = "导出 INI 切换"
    bl_description = "将 INI 切换逻辑变量作为可导入的 .json 文本输出到当前文本编辑器的 IniTogglesExportText 文件中"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        cfg = context.scene.wwmi_tools_settings
        
        text_name = "IniTogglesExportText"

        if text_name in bpy.data.texts:
            text = bpy.data.texts[text_name]
        else:
            text = bpy.data.texts.new(text_name)
        
        text.clear()
        text.write(json.dumps(cfg.ini_toggles.export_vars(), indent=4))
        text.cursor_set(0)

        # Switch the area to TEXT_EDITOR and assign the text
        for area in context.screen.areas:
            area.type = 'TEXT_EDITOR'
            for space in area.spaces:
                if space.type == 'TEXT_EDITOR':
                    space.text = text

        return {'FINISHED'}


class WWMI_TOOLS_ImportIniToggles(bpy.types.Operator):
    bl_idname = "wwmi_tools.import_ini_toggles"
    bl_label = "导入 INI 切换"
    bl_description = "从当前文件的 .json 文本中导入 INI 切换逻辑变量"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        cfg = context.scene.wwmi_tools_settings
        
        text = None
        for area in context.screen.areas:
            if area.type == 'TEXT_EDITOR':
                for space in area.spaces:
                    if space.type == 'TEXT_EDITOR' and space.text:
                        text = space.text
                        break
        try:
            if text is None:
                raise ValueError(f'文本编辑器区域没有打开文本文件!')
            try:
                data = json.loads(text.as_string())
            except Exception as e:
                raise ValueError(f'未知数据格式 (不是 JSON 字典)') from e
            imported_vars_count, skipped_vars_count = cfg.ini_toggles.import_vars(
                data, cfg.ini_toggles.replace_vars_on_import, cfg.ini_toggles.clear_vars_on_import
            )
            msg = f'已导入 {imported_vars_count} INI 切换逻辑变量'
            if skipped_vars_count > 0:
                msg += f' (跳过 {skipped_vars_count} 重复项)'
            self.report({'INFO'}, msg)
        except Exception as e:
            self.report({'ERROR'}, f'导入 INI 切换逻辑变量失败: {e}')
            # Roll back the operator's changes
            bpy.ops.ed.undo()
            return {'CANCELLED'}

        return {'FINISHED'}
    

class WWMI_TOOLS_PT_TEXT_EDITOR_IniToggles(bpy.types.Panel):
    bl_label = "INI 切换 - WWMI Tools"
    bl_space_type = "TEXT_EDITOR"
    bl_region_type = "UI"
    bl_category = "Text"

    def draw(self, context):
        layout = self.layout
        cfg = context.scene.wwmi_tools_settings
        layout.operator(WWMI_TOOLS_ExportIniToggles.bl_idname)
        layout.operator(WWMI_TOOLS_ImportIniToggles.bl_idname)
        layout.prop(cfg.ini_toggles, 'replace_vars_on_import')
        layout.prop(cfg.ini_toggles, 'clear_vars_on_import')
