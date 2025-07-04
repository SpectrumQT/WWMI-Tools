import bpy

from ....migoto_io.blender_interface.objects import *
from ....blender_export.text_formatter import TextFormatter


text_formatter = TextFormatter()


class ToggleVarStateCondition(bpy.types.PropertyGroup):
    logic: bpy.props.EnumProperty(
        description = "控制多个条件如何影响对象的显示",
        items=[
            ('&&', 'AND', """只有当这个条件和上一个条件都为 TRUE 时, 对象才会显示. AND 条件的运算优先级高于 OR 条件
逻辑运算符中的逻辑与: &&, 可以理解为并且, 只有当两个条件的bool值都为True时最后的结果才为True.
(例如: if $active == 1 && %swapvar == 1) 这里如果两个变量的值都为'1(True)', 那么满足逻辑与的条件, 最后的结果也会为True, 结果为True以后就会进入if的语句块内部, 反之如果两个变量的值里
只要有一个不满足等于1这个条件, 那么也就不满足逻辑与的条件, 最后的结果就会是False, 结果为False以后就不会执行if语句块
这些概念需要一定的编程基础, 如果有不懂的可以去查阅文档或者询问AI"""),
            ('||', 'OR', """只有当这个条件为 TRUE 时, 对象才会显示. AND 条件的运算优先级高于 OR 条件
逻辑运算符中的逻辑或: &&, 可以理解为或者, 两个条件做判断时, 只要有一个条件的结果为True, 那么整个表达式的结果就是True
(例如: if $active == 1 || $swapvar == 1) 这里的两个变量里只有一个满足等于1(True)的这个条件, 那么整个表达式的结果就是True
这些概念需要一定的编程基础, 如果有不懂的可以去查阅文档或者询问AI"""),
        ],
        default=0,
    ) # type: ignore
    type: bpy.props.EnumProperty(
        description = "允许在 INI 切换变量和自定义 INI 变量之间切换",
        items=[
            ('TOGGLE', 'Toggle(切换)', '将条件绑定到现有的 INI 切换变量'),
            ('EXTERNAL', 'Custom(自定义)', '将条件绑定到自定义 INI 变量'),
        ],
        default=0,
    ) # type: ignore

    var: bpy.props.StringProperty(
        description = "用于与状态值进行比较的变量.\n提示: 在自定义变量的名称前添加 $ 前缀，以防止其自动格式化为 '$swapvar_name'",
    ) # type: ignore
    operator: bpy.props.EnumProperty(
        description = "控制变量如何与指定值进行比较，以使条件返回 TRUE",
        items=[
            ('==', '==', '变量必须等于指定值.'),
            ('!=', '!=', '变量必须不等于指定值.'),
            ('>', '>', '变量必须大于指定值.'),
            ('<', '<', '变量必须小于指定值.'),
            ('>=', '>=', '变量必须大于或等于指定值.'),
            ('<=', '<=', '变量必须小于或等于指定值.'),
        ],
        default=0,
    ) # type: ignore
    state: bpy.props.StringProperty(
        description = "变量将与之进行比较的状态值"
    ) # type: ignore

    def __str__(self):
        var_name = self.var.strip()
        if not var_name:
            raise ValueError(f'变量名称未设置')
        if not self.state:
            raise ValueError(f'状态未设置')
        if self.type == 'EXTERNAL' and var_name.startswith('$'):
            pass  # Use var name as it is, without any formatting
        else:
            var_name = text_formatter.format_ini_swapvar(var_name)
        return f"{var_name} {self.operator} {self.state}"


class ToggleVarStateObject(bpy.types.PropertyGroup):
    object: bpy.props.PointerProperty(
        type=bpy.types.Object,
        description = "当选择默认条件时, 只有当这个变量处于这个状态 (即变量值等于状态名称中的数字) 时, 对象才会可见",
    ) # type: ignore
    conditions: bpy.props.CollectionProperty(type=ToggleVarStateCondition) # type: ignore

    def update_var_name(self, old_name, new_name):
        for condition in self.conditions:
            if condition.var == old_name:
                condition.var = new_name

    def update_state_name(self, var_name, old_name, new_name):
        for condition in self.conditions:
            if condition.var == var_name and condition.state == old_name:
                condition.state = new_name

    def add_new_condition(self):
        self.conditions.add()
        return self.conditions[-1]

    def add_default_condition(self, var_name, var_state):
        condition = self.add_new_condition()
        condition.logic = '&&'
        condition.type = 'TOGGLE'
        condition.var = var_name
        condition.operator = '=='
        condition.state = var_state

    def format_conditions(self):
        result = ''
        for i, condition in enumerate(self.conditions):
            if i != 0:
                result += ' ' + condition.logic + ' '
            try:
                result += str(condition)
            except Exception as e:
                raise ValueError(f'Condition {i}: {e}') from e
        return result
    
    def has_custom_conditions(self, var_name, var_state):
        for condition in self.conditions:
            if condition.var != var_name or condition.state != var_state or condition.operator != '==':
                return True


class ToggleVarState(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty() # type: ignore
    objects: bpy.props.CollectionProperty(type=ToggleVarStateObject) # type: ignore

    def update_var_name(self, old_name, new_name):
        for state_object in self.objects:
            state_object.update_var_name(old_name, new_name)

    def update_state_name(self, var_name, old_name, new_name):
        for state_object in self.objects:
            state_object.update_state_name(var_name, old_name, new_name)

    def add_new_state_object(self, var_name):
        self.objects.add()
        state_object = self.objects[-1]
        state_object.add_default_condition(var_name, self.name)
        return state_object
    

class ToggleVar(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(
        update=lambda self, context: self.handle_name_update(context),
    ) # type: ignore
    old_name: bpy.props.StringProperty(
    ) # type: ignore
    states: bpy.props.CollectionProperty(type=ToggleVarState) # type: ignore
    default_state: bpy.props.StringProperty(
        name = "默认状态",
    ) # type: ignore
    hotkeys: bpy.props.StringProperty(
        name = "热键",
        description = "用于在变量的不同状态之间切换的键绑定. 使用空格作为组合键的分隔符, 并使用 ';' 分隔同一个变量的多个键绑定.",
    ) # type: ignore
    ui_expanded: bpy.props.BoolProperty(
        name = "切换折叠状态",
        description = "进入或退出这个变量的编辑模式",
        default = True
    ) # type: ignore
    
    def handle_name_update(self, context):
        cfg = context.scene.wwmi_tools_settings

        if not self.name.strip():
            self.set_default_name(cfg.ini_toggles.vars)

        new_name = text_formatter.dedupe_name(self.name, [var.name for var in cfg.ini_toggles.vars if var != self])

        if self.old_name and self.old_name != new_name:
            for var in cfg.ini_toggles.vars:
                var.update_var_name_in_states(self.old_name, new_name)

        self.old_name = new_name

        if self.name != new_name:
            self.name = new_name

    def update_var_name_in_states(self, old_name, new_name):
        for state in self.states:
            state.update_var_name(old_name, new_name)

    def set_default_name(self, vars):
        var_names = [var.name for var in vars]
        for i in range(1024):
            var_name = f'TOGGLE_{i}'
            if var_name in var_names:
                continue
            self.name = var_name
            break

    def add_empty_state(self):
        self.states.add()
        state = self.states[-1]
        state.name = '-1'
        return state

    def add_new_state(self):
        prev_state_id = int(self.states[-1].name)
        self.states.add()
        state = self.states[-1]
        state.name = f'{prev_state_id+1}'
        state.add_new_state_object(self.name)
        if len(self.states) == 1:
            self.default_state = state.name
        return state
    
    def remove_state(self, idx):
        state = self.states[idx]
        # Skip removal of default empty state "-1"
        if state.name == "-1":
            return
        self.states.remove(idx)
        # Renumerate state names
        if len(self.states) < idx:
            return
        state_id = int(self.states[idx-1].name)
        for state in self.states[idx:]:
            state_id += 1
            new_state_name = str(state_id)
            # Update var's default state name
            if self.default_state == state.name:
                self.default_state = new_state_name
            # Update state name
            state.name = new_state_name
            # Update state name in conditions
            for state_object in state.objects:
                for condition in state_object.conditions:
                    if condition.var == self.name and condition.state == state.name and condition.operator == '==':
                        continue
                    condition.state = state.name
    
    def swap_states(self, scr_idx, dst_idx):
        scr_state = self.states[scr_idx]
        dst_state = self.states[dst_idx]

        scr_name = scr_state.name
        dst_name = dst_state.name
        scr_state.name = dst_name
        dst_state.name = scr_name

        scr_state.update_state_name(self.name, scr_name, dst_name)
        dst_state.update_state_name(self.name, dst_name, scr_name)

        self.states.move(scr_idx, dst_idx)

    def get_formatted_hotkeys(self, join_arg=' '):
        return text_formatter.format_hotkeys(self.hotkeys, join_arg=join_arg)

    def get_hotkeys(self):
        """
        Deprecated: use get_formatted_hotkeys instead
        """
        return text_formatter.extract_hotkeys_parts(self.hotkeys)


class IniToggles(bpy.types.PropertyGroup):
    vars: bpy.props.CollectionProperty(
        type=ToggleVar,
    ) # type: ignore

    replace_vars_on_import: bpy.props.BoolProperty(
        name="在导入时替换现有变量",
        description="用导入的变量替换已存在的同名 INI 切换逻辑变量 (如果禁用，重复项将被跳过)",
        default=True,
    ) # type: ignore

    clear_vars_on_import: bpy.props.BoolProperty(
        name="在导入时清除现有变量",
        description="在导入变量之前移除所有现有的 INI 切换逻辑变量",
        default=False,
    ) # type: ignore

    hide_empty_states: bpy.props.BoolProperty(
        name="隐藏没有对象的\"-1\"状态",
        description="从用户界面中隐藏空的\"-1\"状态, 以节省空间",
        default=False
    ) # type: ignore

    hide_default_conditions: bpy.props.BoolProperty(
        name="隐藏默认条件",
        description="从用户界面中隐藏默认条件, 以节省空间",
        default=False
    ) # type: ignore

    def add_new_var(self):
        self.vars.add()
        var = self.vars[-1]
        var.set_default_name(self.vars)
        var.add_empty_state()
        state_0 = var.add_new_state()
        var.default_state = state_0.name
        return var

    def collection_to_list(self, collection):
        result = []
        for item in collection:
            item_data = {}
            for prop in item.bl_rna.properties:
                if prop.identifier in {"rna_type"}:
                    continue  # Skip internal properties
                value = getattr(item, prop.identifier)
                if isinstance(value, bpy.types.bpy_prop_collection):
                    item_data[prop.identifier] = self.collection_to_list(value)
                elif isinstance(value, bpy.types.Object):
                    item_data[prop.identifier] = value.name
                else:
                    item_data[prop.identifier] = value
            result.append(item_data)
        return result

    def list_to_collection(self, data, collection):
        for item_dict in data:
            new_item = collection.add()
            for key, value in item_dict.items():
                if not hasattr(new_item, key):
                    continue
                attr = getattr(new_item, key)
                if hasattr(new_item.__class__, 'bl_rna'):
                    prop = new_item.__class__.bl_rna.properties[key]
                else:
                    prop = None
                # If it's a nested collection, recurse
                if isinstance(attr, bpy.types.bpy_prop_collection) and isinstance(value, list):
                    self.list_to_collection(value, attr)
                # If it's a pointer to object, resolve
                elif isinstance(prop, bpy.types.PointerProperty) and prop.fixed_type.name == 'Object' and value is not None:
                    setattr(new_item, key, get_object(value))
                # Otherwise, set simple value
                else:
                    try:
                        setattr(new_item, key, value)
                    except Exception as e:
                        print(f"Error setting '{key}' = {value}: {e}")

    def export_vars(self):
        return {
            'format_type': 'IniToggleVars',
            'format_version': '1.0',
            'data': self.collection_to_list(self.vars),
        }
    
    def import_vars(self, data, replace_vars = False, clear_vars = False):
        if not isinstance(data, dict):
            raise ValueError(f'Unknown data format (not a dict)')
        format_type = data.get('format_type', None)
        if format_type is None:
            raise ValueError(f'Unknown data format (format_type not specified)')
        format_type = str(format_type).strip()
        if format_type != 'IniToggleVars':
            raise ValueError(f'Invalid data format type `{format_type}` (expected `IniToggleVars`)')
        format_version = data.get('format_version', None)
        if format_version is None:
            raise ValueError(f'Unknown data format (format_version not specified)')
        format_version = str(format_version).strip()
        if format_version < '1.0':
            raise ValueError(f'Unknown data format version `{format_version}` (expected at least `1.0`)')
        if format_version > '1.0':
            raise ValueError(f'Installed WWMI Tools version does not support `{format_version}` data format version, please check for available addon updates!')
        
        vars_data = data['data']

        if clear_vars:
            self.vars.clear()
        else:
            if replace_vars:
                for var_data in vars_data:
                    for var_id, var in enumerate(list(self.vars)):
                        if var.name == var_data['name']:
                            self.vars.remove(self.vars.find(var.name))
            else:
                var_names = [var.name for var in self.vars]
                vars_data = [var_data for var_data in vars_data if var_data['name'] not in var_names]

        self.list_to_collection(vars_data, self.vars)

        imported_vars_count = len(vars_data)
        skipped_vars_count = len(data['data']) - imported_vars_count

        return imported_vars_count, skipped_vars_count

    def compile_conditions(self):
        conditions = {}
        for var in self.vars:
            for state in var.states:
                for obj_id, obj in enumerate(state.objects):
                    try:
                        if not obj.object:
                            raise ValueError(f'Object {obj_id} is not set')
                        if obj.object.name in conditions.keys():
                            conditions[obj.object.name] += f' || ({obj.format_conditions()})'
                        else:
                            conditions[obj.object.name] = f'({obj.format_conditions()})'
                    except Exception as e:
                        raise ValueError(f'Ini Toggles error in State `{state.name}` of Var `{var.name}`:\n{e}') from e
        return conditions
