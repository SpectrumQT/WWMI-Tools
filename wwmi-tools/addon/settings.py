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
        name="Mode",
        description="Defines list of available actions",
        items=[
            ('EXPORT_MOD', 'Export Mod', 'Export selected collection as WWMI mod'),
            ('IMPORT_OBJECT', 'Import Object', 'Import .ib ad .vb files from selected directory'),
            ('EXTRACT_FRAME_DATA', 'Extract Objects From Dump', 'Extract components of all WWMI-compatible objects from the selected frame dump directory'),
            ('TOOLS_MODE', 'Toolbox', 'Bunch of useful object actions'),
        ],
        update=lambda self, context: clear_error(self),
        default=0,
    ) # type: ignore

    ########################################
    # Extract Frame Data
    ########################################

    frame_dump_folder: StringProperty(
        name="Frame Dump",
        description="Frame dump files directory",
        default='',
        subtype="DIR_PATH",
        update=lambda self, context: self.on_update_clear_error('frame_dump_folder'),
    ) # type: ignore

    allow_missing_shapekeys: BoolProperty(
        name="Extract Objects With Missing Shapekeys",
        description="Do not skip extraction of objects with missing shapekeys data (normally user should re-dump during some facial animation).",
        default=False,
    ) # type: ignore

    skip_small_textures: BoolProperty(
        name="Textures Filtering: Skip Small",
        description="Skip texture smaller than specified size",
        default=True,
    ) # type: ignore

    skip_small_textures_size: IntProperty(
        name="Min Size (KB)",
        description="Minimal texture size in KB. Default is 256KB",
        default=256,
    ) # type: ignore

    skip_jpg_textures: BoolProperty(
        name="Textures Filtering: Skip .jpg",
        description="Skip texture with .jpg extension. These textures are mostly gradients and other masks",
        default=True,
    ) # type: ignore

    skip_same_slot_hash_textures: BoolProperty(
        name="Textures Filtering: Skip Same Slot-Hash",
        description="Skip texture if its hash is found in same slot of all components. May filter out useful textures!",
        default=False,
    ) # type: ignore

    extract_output_folder: StringProperty(
        name="Output Folder",
        description="Extracted WWMI objects export directory",
        default='',
        subtype="DIR_PATH",
    ) # type: ignore

    ########################################
    # Object Import
    ########################################

    object_source_folder: StringProperty(
        name="Object Sources",
        description="Directory with components and textures of WWMI object",
        default='',
        subtype="DIR_PATH",
        update=lambda self, context: self.on_update_clear_error('object_source_folder'),
    ) # type: ignore

    import_skeleton_type: bpy.props.EnumProperty(
        name="Skeleton",
        description="Controls the way of Vertex Groups handling",
        items=[
            ('MERGED', 'Merged', 'Imported mesh will have unified list of Vertex Groups, allowing to weight any vertex of any component to any bone. Mod Upsides: easy to weight, custom skeleton scale support, advanced weighting support (i.e. long hair to cape). Mod Downsides: model will be updated with 1 frame delay, mod will pause while there are more than one of same modded object on screen. Suggested usage: new modders, character or echo mods with complex weights.'),
            ('COMPONENT', 'Per-Component', 'Imported mesh will have its Vertex Groups split into per component lists, restricting weighting of any vertex only to its parent component. Mod Upsides: no 1-frame delay for model updates, minor performance gain. Mod downsides: hard to weight, very limited weighting options, no custom skeleton scale support. Suggested usage: weapon mods and simple retextures.'),
        ],
        default=0,
    ) # type: ignore

    mirror_mesh: BoolProperty(
        name="Mirror Mesh",
        description="Automatically mirror mesh to match actual in-game left-right. Transformation applies to the data itself and does not affect Scale X of Transform section in Object Properties.",
        default=False,
    ) # type: ignore

    color_storage: bpy.props.EnumProperty(
        name="Vertex Colors",
        description="Controls how color data is handled",
        items=[
            ('LINEAR', 'Linear', 'Display vertex colors as they actually are and store them with full float precision. Handle colors via `color_attributes`'),
            ('LEGACY', 'sRGB (legacy)', 'Display vertex colors as sRGB shifted and store them with 8-bit float precision. Handle colors via deprecated `vertex_colors`'),
        ],
        default='LINEAR',
    ) # type: ignore

    ########################################
    # Mod Export
    ########################################
        
    component_collection: PointerProperty(
        name="Components",
        description="Collection with WWMI object's components named like `Component 0` or `Component_1 RedHat` or `Dat Gas cOmPoNENT- 3 OMG` (lookup RegEx: r'.*component[_ -]*(\d+).*')",
        type=bpy.types.Collection,
        update=lambda self, context: self.on_update_clear_error('component_collection'),
        # default=False
    ) # type: ignore

    mod_output_folder: StringProperty(
        name="Mod Folder",
        description="Mod export directory to place mod.ini and Meshes&Textures folders into",
        default='',
        subtype="DIR_PATH",
        update=lambda self, context: self.on_update_clear_error('mod_output_folder'),
    ) # type: ignore
    
    apply_modifiers: BoolProperty(
        name="Apply Modifiers",
        description="Apply all modifiers to temporary copy of the merged object",
        default=False,
    ) # type: ignore

    mod_name: StringProperty(
        name="Mod Name",
        description="Name of mod to be displayed in user notifications and mod managers",
        default='Unnamed Mod',
    ) # type: ignore

    mod_author: StringProperty(
        name="Author Name",
        description="Name of mod author to be displayed in user notifications and mod managers",
        default='Unknown Author',
    ) # type: ignore

    mod_desc: StringProperty(
        name="Mod Description",
        description="Short mod description to be displayed in user notifications and mod managers",
        default='',
    ) # type: ignore

    mod_link: StringProperty(
        name="Mod Link",
        description="Link to mod web page to be displayed in user notifications and mod managers",
        default='',
    ) # type: ignore

    mod_logo: StringProperty(
        name="Mod Logo",
        description="Texture with 512x512 size and .dds extension (BC7 SRGB) to be displayed in user notifications and mod managers, will be placed to /Textures/Logo.dds",
        default='',
        subtype="FILE_PATH",
    ) # type: ignore

    mod_skeleton_type: bpy.props.EnumProperty(
        name="Skeleton",
        description="Select the same skeleton type that was used for import! Defines logic of exported mod.ini.",
        items=[
            ('MERGED', 'Merged', 'Mesh with this skeleton should have unified list of Vertex Groups'),
            ('COMPONENT', 'Per-Component', 'Mesh with this skeleton should have its Vertex Groups split into per-component lists.'),
        ],
        default=0,
    ) # type: ignore

    partial_export: BoolProperty(
        name="Partial Export",
        description="For advanced usage only. Allows to export only selected buffers. Speeds up export when you're sure that there were no changes to certain data since previous export. Disables INI generation and assets copying",
        default=False,
    ) # type: ignore

    export_index: BoolProperty(
        name="Index Buffer",
        description="Contains data that associates vertices with faces",
        default=True,
    ) # type: ignore

    export_positions: BoolProperty(
        name="Position Buffer",
        description="Contains coordinates of each vertex",
        default=True,
    ) # type: ignore

    export_blends: BoolProperty(
        name="Blend Buffer",
        description="Contains VG ids and weights of each vertex",
        default=True,
    ) # type: ignore

    export_vectors: BoolProperty(
        name="Vector Buffer",
        description="Contains normals and tangents",
        default=True,
    ) # type: ignore

    export_colors: BoolProperty(
        name="Color Buffer",
        description="Contains vertex color attribute named COLOR",
        default=True,
    ) # type: ignore

    export_texcoords: BoolProperty(
        name="TexCoord Buffer",
        description="Contains UVs and vertex color attribute named COLOR1",
        default=True,
    ) # type: ignore

    export_shapekeys: BoolProperty(
        name="Shape Keys Buffers",
        description="Contains shape keys data",
        default=True,
    ) # type: ignore
    
    ignore_nested_collections: BoolProperty(
        name="Ignore Nested Collections",
        description="If enabled, objects inside nested collections inside Components collection won't be exported",
        default=True,
    ) # type: ignore

    ignore_hidden_collections: BoolProperty(
        name="Ignore Hidden Collections",
        description="If enabled, objects from hidden nested collections inside Components collection won't be exported",
        default=True,
    ) # type: ignore
    
    ignore_hidden_objects: BoolProperty(
        name="Ignore Hidden Objects",
        description="If enabled, hidden objects inside Components collection won't be exported",
        default=False,
    ) # type: ignore
    
    ignore_muted_shape_keys: BoolProperty(
        name="Ignore Muted Shape Keys",
        description="If enabled, muted (unchecked) shape keys won't be exported",
        default=True,
    ) # type: ignore

    apply_all_modifiers: BoolProperty(
        name="Apply All Modifiers",
        description="Automatically apply all existing modifiers to temporary copies of each object",
        default=False,
    ) # type: ignore

    copy_textures: BoolProperty(
        name="Copy Textures",
        description="Copy texture files to export folder",
        default=True,
    ) # type: ignore

    write_ini: BoolProperty(
        name="Write Mod INI",
        description="Write new .ini to export folder",
        default=True,
    ) # type: ignore

    comment_ini: BoolProperty(
        name="Comment INI code",
        description="Add comments to INI code, useful if you want to get better idea how it works",
        default=False,
    ) # type: ignore

    skeleton_scale: FloatProperty(
        name="Skeleton Scale",
        description="Scales model in-game (default is 1.0). Not supported for Per-Component Skeleton",
        default=1.0,
    ) # type: ignore

    unrestricted_custom_shape_keys: BoolProperty(
        name="Unrestricted Custom Shape Keys",
        description="Allows to use Custom Shape Keys for components that don't have them by default. Generates extra mod.ini logic",
        default=False,
    ) # type: ignore

    remove_temp_object: BoolProperty(
        name="Remove Temp Object",
        description="Remove temporary object built from merged components after export. May be useful to uncheck for debug purposes",
        default=True,
    ) # type: ignore

    export_on_reload: BoolProperty(
        name="Export On Reload",
        description="Trigger mod export on addon reload. Useful for export debugging.",
        default=False,
    ) # type: ignore

    use_custom_template: BoolProperty(
        name="Use Custom Template",
        description="Use configured jinja2 template to build fully custom mod.ini.",
        default=False,
        update=lambda self, context: self.on_update_clear_error('use_custom_template'),
    ) # type: ignore

    custom_template_live_update: BoolProperty(
        name="Template Live Updates",
        description="Controls state of live ini generation thread.",
        default=False,
    ) # type: ignore

    custom_template_source: bpy.props.EnumProperty(
        name="Storage",
        description="Select custom template storage type.",
        items=[
            ('INTERNAL', 'Built-in Editor', 'Use Blender scripting tab file as custom template.'),
            ('EXTERNAL', 'External File', 'Use specified file as custom template.'),
        ],
        default=0,
        update=lambda self, context: self.on_update_clear_error('use_custom_template'),
    ) # type: ignore

    custom_template_path: StringProperty(
        name="Custom Template File",
        description="Path to mod.ini template file.\nTo create new file, copy template text from built-in editor to new text file.",
        default='',
        subtype="FILE_PATH",
        update=lambda self, context: self.on_update_clear_error('custom_template_path'),
    ) # type: ignore

    last_error_setting_name: StringProperty(
        name="Last Error Setting Name",
        description="Name of setting property which was cause of last error.",
        default='component_collection',
    ) # type: ignore

    last_error_text: StringProperty(
        name="Last Error Text",
        description="Text of last error.",
        default='Collection must be filled!',
    ) # type: ignore

    use_ini_toggles: BoolProperty(
        name="Use Ini Toggles",
        description="Add configured Ini Toggles logic to mod.ini",
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
        name="Auto-check for Update",
        description="If enabled, auto-check for updates using an interval",
        default=True) # type: ignore

    updater_interval_months: IntProperty(
        name='Months',
        description="Number of months between checking for updates",
        default=0,
        min=0) # type: ignore

    updater_interval_days: IntProperty(
        name='Days',
        description="Number of days between checking for updates",
        default=1,
        min=0,
        max=31) # type: ignore

    updater_interval_hours: IntProperty(
        name='Hours',
        description="Number of hours between checking for updates",
        default=0,
        min=0,
        max=23) # type: ignore

    updater_interval_minutes: IntProperty(
        name='Minutes',
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
