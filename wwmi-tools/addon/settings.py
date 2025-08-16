import bpy

from bpy.props import BoolProperty, StringProperty, PointerProperty, IntProperty, FloatProperty, CollectionProperty

from .. import bl_info
from .. import __name__ as package_name
from .. import addon_updater_ops

from .modules.ini_toggles.props import IniToggles

from .exceptions import clear_error


class WWMI_Settings(bpy.types.PropertyGroup):

    def on_update_clear_error(self, property_name):
        if self.last_error_setting_name == property_name:
            clear_error(self)

    wwmi_tools_version: bpy.props.StringProperty(
        name = "WWMI Tools Version",
        default = '.'.join(map(str, bl_info["version"]))
    ) # type: ignore

    required_wwmi_version: bpy.props.StringProperty(
        name = "Required WWMI Version",
        default = '.'.join(map(str, bl_info["wwmi_version"]))
    ) # type: ignore

    vertex_ids_cache: bpy.props.StringProperty(
        name = "Vertex Ids Cache",
        default = ""
    ) # type: ignore

    index_data_cache: bpy.props.StringProperty(
        name = "Index Data Cache",
        default = ""
    ) # type: ignore
    
    vertex_ids_cached_collection: PointerProperty(
        name="Loop Data Cached Components",
        type=bpy.types.Collection,
    ) # type: ignore

    tool_mode: bpy.props.EnumProperty(
        name="模式",
        description="选择可用于操作的列表",
        items=[
            ('EXPORT_MOD', '导出模组', '将选定的集合导出为 WWMI 模组'),
            ('IMPORT_OBJECT', '导入对象', '从选定目录导入 .ib 和 .vb 文件'),
            ('EXTRACT_FRAME_DATA', '从帧转储中提取对象', '从选定的帧转储目录中提取所有兼容 WWMI 对象的组件'),
            ('TOOLS_MODE', '工具箱', '一系列实用的工具'),
        ],
        update=lambda self, context: clear_error(self),
        default=0,
    ) # type: ignore

    ########################################
    # Extract Frame Data
    ########################################

    frame_dump_folder: StringProperty(
        name="帧转储文件夹",
        description="选择帧转储文件夹",
        default='',
        subtype="DIR_PATH",
        update=lambda self, context: self.on_update_clear_error('frame_dump_folder'),
    ) # type: ignore

    allow_missing_shapekeys: BoolProperty(
        name="提取缺少形态键的对象",
        description="不要跳过缺少形态键数据的对象的提取 (通常用户应该在某些面部动画期间重新转储)",
        default=False,
    ) # type: ignore

    skip_small_textures: BoolProperty(
        name="纹理过滤: 跳过小尺寸纹理",
        description="跳过小于指定尺寸的纹理",
        default=True,
    ) # type: ignore

    skip_small_textures_size: IntProperty(
        name="最小尺寸 (KB)",
        description="最小纹理大小 (以 KB 为单位). 默认值为 256KB",
        default=256,
    ) # type: ignore

    skip_jpg_textures: BoolProperty(
        name="纹理过滤: 跳过.jpg",
        description="跳过扩展名为.jpg的纹理, 这些纹理大多是渐变和其他遮罩",
        default=True,
    ) # type: ignore

    skip_same_slot_hash_textures: BoolProperty(
        name="纹理过滤: 跳过相同槽位哈希",
        description="如果其哈希值在所有组件的相同槽位中被找到，则跳过该纹理。可能会过滤掉有用的纹理!",
        default=False,
    ) # type: ignore

    extract_output_folder: StringProperty(
        name="输出文件夹",
        description="选择提取的 WWMI 对象的导出文件夹",
        default='',
        subtype="DIR_PATH",
    ) # type: ignore

    ########################################
    # Object Import
    ########################################

    object_source_folder: StringProperty(
        name="对象来源",
        description="WWMI 对象的组件和纹理所在的文件夹",
        default='',
        subtype="DIR_PATH",
        update=lambda self, context: self.on_update_clear_error('object_source_folder'),
    ) # type: ignore

    import_skeleton_type: bpy.props.EnumProperty(
        name="骨架类型",
        description="控制模型顶点组处理的方式",
        items=[
            ('MERGED', '合并骨架', """
导入的网格将具有统一的顶点组列表，允许将任何组件的任何顶点权重分配给任何骨骼. 
优点: 容易进行权重分配, 支持自定义骨骼比例, 支持高级权重功能 (例如: 将长发权重分配到斗篷)
缺点: 模型更新会有 1 帧延迟, 当屏幕上存在多个相同的模组对象时, 模组会崩溃.
建议使用场景: 新手模组制作者, 以及具有复杂权重的角色或声骸模组"""),
            ('COMPONENT', '按组件', """
导入的网格将把其顶点组拆分为每个组件的独立列表, 限制任何顶点的权重仅分配给其父组件
优点: 模型更新不会出现 1 帧延迟, 性能略有提升
缺点: 加权难度较大, 非常有限的加权选项, 不支持自定义骨架缩放.
建议使用场景: 武器模组 和 简单的纹理替换"""),
        ],
        default=0,
    ) # type: ignore

    mirror_mesh: BoolProperty(
        name="镜像网格",
        description="自动镜像网格以匹配游戏中实际的左右方向. 这种变换会直接应用于数据本身, 而不会影响对象属性中变换部分的X轴缩放值",
        default=False,
    ) # type: ignore

    ########################################
    # Mod Export
    ########################################
        
    component_collection: PointerProperty(
        name="组件",
        description="包含WWMI对象组件的集合，组件名称类似于Component 0或Component_1 RedHat或Dat Gas cOmPoNENT- 3 OMG (查找正则表达式：r'.*component[_ -]*(\d+).*')",
        type=bpy.types.Collection,
        update=lambda self, context: self.on_update_clear_error('component_collection'),
        # default=False
    ) # type: ignore

    mod_output_folder: StringProperty(
        name="模组文件夹",
        description="模组的导出文件夹, 用于放置 mod.ini 文件以及 Meshes 和 Textures 文件夹",
        default='',
        subtype="DIR_PATH",
        update=lambda self, context: self.on_update_clear_error('mod_output_folder'),
    ) # type: ignore
    
    apply_modifiers: BoolProperty(
        name="应用修改器",
        description="将所有修改器应用于合并对象的临时副本",
        default=False,
    ) # type: ignore

    mod_name: StringProperty(
        name="模组名称",
        description="模组名称, 用于在用户通知和模组管理器中显示",
        default='无名模组',
    ) # type: ignore

    mod_author: StringProperty(
        name="作者名称",
        description="模组作者的名称, 用于在用户通知和模组管理器中显示",
        default='未知作者',
    ) # type: ignore

    mod_desc: StringProperty(
        name="模组描述",
        description="简短的模组描述, 用于在用户通知和模组管理器中显示",
        default='',
    ) # type: ignore

    mod_link: StringProperty(
        name="模组链接",
        description="模组网页的链接, 用于在用户通知和模组管理器中显示",
        default='',
    ) # type: ignore

    mod_logo: StringProperty(
        name="模组 Logo",
        description="大小为 512x512 且扩展名为 .dds (BC7 SRGB 格式) 的纹理, 用于在用户通知和模组管理器中显示, 将被放置到 /Textures/Logo.dds",
        default='',
        subtype="FILE_PATH",
    ) # type: ignore

    mod_skeleton_type: bpy.props.EnumProperty(
        name="骨架类型",
        description="选择与导入时使用的相同骨骼类型!这将决定导出的 mod.ini 文件的逻辑",
        items=[
            ('MERGED', '合并骨架', '具有这种骨架的网格会有一个统一的顶点组列表'),
            ('COMPONENT', '按组件', '具有这种骨架的网格应该将其顶点组拆分为每个组件的独立列表'),
        ],
        default=0,
    ) # type: ignore

    partial_export: BoolProperty(
        name="部分缓冲区导出",
        description="仅适用于高级用途. 允许仅导出选定的缓冲区. 在你确信某些数据自上次导出以来未发生变化时, 可以加快导出速度. 此选项会禁用 INI 文件生成和对象资产的复制",
        default=False,
    ) # type: ignore

    export_index: BoolProperty(
        name="索引缓冲区 (Index Buffer)",
        description="包含将顶点与面相关联的数据",
        default=True,
    ) # type: ignore

    export_positions: BoolProperty(
        name="位置缓冲区 (Position Buffer)",
        description="包含每个顶点的坐标",
        default=True,
    ) # type: ignore

    export_blends: BoolProperty(
        name="混合缓冲区 (Blend Buffer)",
        description="包含每个顶点的顶点组ID和权重",
        default=True,
    ) # type: ignore

    export_vectors: BoolProperty(
        name="向量缓冲区 (Vector Buffer)",
        description="包含模型的法线和切线",
        default=True,
    ) # type: ignore

    export_colors: BoolProperty(
        name="顶点颜色缓冲区 (Color Buffer)",
        description="包含名为 COLOR 的顶点颜色属性",
        default=True,
    ) # type: ignore

    export_texcoords: BoolProperty(
        name="纹理坐标缓冲区 (TexCoord Buffer)",
        description="包含 UV 坐标和名为 COLOR1 的顶点颜色属性",
        default=True,
    ) # type: ignore

    export_shapekeys: BoolProperty(
        name="形态键缓冲区 (Shape Keys Buffer)",
        description="包含形态键数据",
        default=True,
    ) # type: ignore
    
    ignore_nested_collections: BoolProperty(
        name="忽略嵌套集合",
        description="如果启用, 组件集合内的嵌套集合中的对象将不会被导出",
        default=True,
    ) # type: ignore

    ignore_hidden_collections: BoolProperty(
        name="忽略隐藏集合",
        description="如果启用, 组件集合内被隐藏的嵌套集合中的对象将不会被导出",
        default=True,
    ) # type: ignore
    
    ignore_hidden_objects: BoolProperty(
        name="忽略隐藏对象",
        description="如果启用, 组件集合内被隐藏的对象将不会被导出",
        default=False,
    ) # type: ignore
    
    ignore_muted_shape_keys: BoolProperty(
        name="忽略禁用的形态键",
        description="如果启用, 被禁用 (未选中) 的形态键将不会被导出",
        default=True,
    ) # type: ignore

    apply_all_modifiers: BoolProperty(
        name="应用全部修改器",
        description="自动将所有现有修改器应用于每个对象的临时副本",
        default=False,
    ) # type: ignore

    copy_textures: BoolProperty(
        name="复制纹理",
        description="将纹理文件复制到导出文件夹",
        default=True,
    ) # type: ignore

    write_ini: BoolProperty(
        name="写入模组 INI",
        description="将新的 .ini 文件写入导出文件夹",
        default=True,
    ) # type: ignore

    comment_ini: BoolProperty(
        name="注释 INI 代码",
        description="在 INI 代码中添加注释, 如果你希望更好地理解其工作原理, 这会很有帮助",
        default=False,
    ) # type: ignore

    skeleton_scale: FloatProperty(
        name="整体骨架缩放",
        description="在游戏中整体缩放模型 (默认值为 1.0) 不支持\"按组件类型的骨架\"",
        default=1.0,
    ) # type: ignore

    unrestricted_custom_shape_keys: BoolProperty(
        name="无限制自定义形态键",
        description="允许为默认情况下没有形态键的组件使用自定义形状键. 会生成额外的 mod.ini 逻辑",
        default=False,
    ) # type: ignore

    remove_temp_object: BoolProperty(
        name="移除临时对象",
        description="在导出后移除由合并组件构建的临时对象. 在调试时可能需要取消勾选",
        default=True,
    ) # type: ignore

    export_on_reload: BoolProperty(
        name="在插件重新加载时导出",
        description="在插件重新加载时触发模组导出. 对于导出调试很有用.",
        default=False,
    ) # type: ignore

    use_custom_template: BoolProperty(
        name="使用自定义模版",
        description="使用配置好的 jinja2 模板来构建完全自定义的 mod.ini 文件.",
        default=False,
        update=lambda self, context: self.on_update_clear_error('use_custom_template'),
    ) # type: ignore

    custom_template_live_update: BoolProperty(
        name="Template Live Updates",
        description="Controls state of live ini generation thread.",
        default=False,
    ) # type: ignore

    custom_template_source: bpy.props.EnumProperty(
        name="存储",
        description="选择自定义模板的存储类型",
        items=[
            ('INTERNAL', '内置编辑器', '使用 Blender 脚本标签中的文件作为自定义模板'),
            ('EXTERNAL', '外部文件', '使用指定的文件作为自定义模板'),
        ],
        default=0,
        update=lambda self, context: self.on_update_clear_error('use_custom_template'),
    ) # type: ignore

    custom_template_path: StringProperty(
        name="自定义模版文件",
        description="模版文件的路径.\n要创建新文件, 请将内置编辑器中的模板文本复制到新的文本文件中",
        default='',
        subtype="FILE_PATH",
        update=lambda self, context: self.on_update_clear_error('custom_template_path'),
    ) # type: ignore

    last_error_setting_name: StringProperty(
        name="上次错误设置名称",
        description="导致上次错误的设置属性名称",
        default='component_collection',
    ) # type: ignore

    last_error_text: StringProperty(
        name="上次错误文本",
        description="上次错误的文本内容.",
        default='集合必须被填充!',
    ) # type: ignore

    use_ini_toggles: BoolProperty(
        name="使用 INI 切换",
        description="将配置好的 INI 切换逻辑添加到 mod.ini",
        default=False,
    ) # type: ignore

    ini_toggles: bpy.props.PointerProperty(
        type=IniToggles,
    ) # type: ignore



class Preferences(bpy.types.AddonPreferences):
    """Preferences updater"""
    bl_idname = package_name
    # Addon updater preferences.

    auto_check_update: BoolProperty(
        name="自动检查更新",
        description="如果启用，则使用指定间隔自动检查更新",
        default=True) # type: ignore

    updater_interval_months: IntProperty(
        name='月',
        description="Number of months between checking for updates",
        default=0,
        min=0) # type: ignore

    updater_interval_days: IntProperty(
        name='天',
        description="Number of days between checking for updates",
        default=1,
        min=0,
        max=31) # type: ignore

    updater_interval_hours: IntProperty(
        name='小时',
        description="Number of hours between checking for updates",
        default=0,
        min=0,
        max=23) # type: ignore

    updater_interval_minutes: IntProperty(
        name='分钟',
        description="Number of minutes between checking for updates",
        default=0,
        min=0,
        max=59) # type: ignore

    def draw(self, context):
        layout = self.layout
        print(addon_updater_ops.get_user_preferences(context))
        # Works best if a column, or even just self.layout.
        mainrow = layout.row()
        col = mainrow.column()
        # Updater draw function, could also pass in col as third arg.
        addon_updater_ops.update_settings_ui(self, context)

        # Alternate draw function, which is more condensed and can be
        # placed within an existing draw function. Only contains:
        #   1) check for update/update now buttons
        #   2) toggle for auto-check (interval will be equal to what is set above)
        # addon_updater_ops.update_settings_ui_condensed(self, context, col)

        # Adding another column to help show the above condensed ui as one column
        # col = mainrow.column()
        # col.scale_y = 2
        # ops = col.operator("wm.url_open","Open webpage ")
        # ops.url=addon_updater_ops.updater.website
