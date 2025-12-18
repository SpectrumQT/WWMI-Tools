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
    

#######################################################

import math
from mathutils import Vector, Matrix

def unit_vector_to_octahedron(n):
    """
    Converts a unit vector to octahedron coordinates.
    n is a mathutils.Vector
    """
    # Ensure input is a unit vector
    if n.length_squared > 1e-10:
        n.normalize()
    else:
        return Vector((0.0, 0.0))
    
    # Calculate L1 norm
    l1_norm = abs(n.x) + abs(n.y) + abs(n.z)
    if l1_norm < 1e-10:
        return Vector((0.0, 0.0))
    
    # Project to octahedron plane
    x = n.x / l1_norm
    y = n.y / l1_norm
    
    # Negative hemisphere mapping (only applied when z < 0)
    if n.z < 0:
        # Use precise sign function
        sign_x = math.copysign(1.0, x)
        sign_y = math.copysign(1.0, y)
        
        # Original mapping formula (preserves good behavior at z=0)
        new_x = (1.0 - abs(y)) * sign_x
        new_y = (1.0 - abs(x)) * sign_y
        
        # Apply new coordinates directly (remove transition interpolation)
        x = new_x
        y = new_y
    
    return Vector((x, y))

def calc_smooth_normals(mesh):
    """Calculate smooth normals (angle-weighted average)"""
    vertex_normals = {}
    
    # Use vertex index as key (avoid floating point precision issues)
    for i, vert in enumerate(mesh.vertices):
        vertex_normals[i] = Vector((0, 0, 0))
    
    # Calculate normal for each face and accumulate to vertices with weighting
    for poly in mesh.polygons:
        verts = [mesh.vertices[i] for i in poly.vertices]
        face_normal = poly.normal
        
        for i, vert in enumerate(verts):
            # Get adjacent edge vectors
            v1 = verts[(i+1) % len(verts)].co - vert.co
            v2 = verts[(i-1) % len(verts)].co - vert.co
            
            # Calculate angle weight
            v1_len = v1.length
            v2_len = v2.length
            if v1_len > 1e-6 and v2_len > 1e-6:
                v1.normalize()
                v2.normalize()
                weight = math.acos(max(-1.0, min(1.0, v1.dot(v2))))
            else:
                weight = 0.0
            
            # Accumulate weighted normals
            vertex_normals[vert.index] += face_normal * weight
    
    # Normalize normals
    for idx in vertex_normals:
        if vertex_normals[idx].length > 1e-6:
            vertex_normals[idx].normalize()
    
    return vertex_normals

class WWMI_TangentSpaceOctahedralUV(bpy.types.Operator):
    """Generate octahedral UV mapping in tangent space"""
    bl_idname = "wwmi_tools.octahedral_uv"
    bl_label = "TEXCOORD1: Smooth Normals - Octahedral UV"
    bl_description = ("For all selected objects\n"
    "Map smooth normals to tangent space coordinates and project to octahedral unwrapping plane\n"
    "Stored in TEXCOORD1\n"
    "A properly unwrapped UV set is required to calculate tangent space")
    bl_options = {'REGISTER', 'UNDO'}
    
    
    @classmethod
    def poll(cls, context):
        """Check if mesh objects can be selected"""
        return context.selected_objects is not None and len(context.selected_objects) > 0
    
    def execute(self, context):
        """Execute the operation"""
        selected_objects = context.selected_objects
        processed_count = 0
        
        for obj in selected_objects:
            if self.process_object(obj):
                processed_count += 1
        
        # Update viewport display
        context.view_layer.update()
        
        if processed_count > 0:
            self.report({'INFO'}, f"Tangent space octahedral UV mapping completed! Processed {processed_count} mesh object(s)")
            return {'FINISHED'}
        else:
            self.report({'WARNING'}, "No mesh objects were processed. Please ensure mesh objects are selected")
            return {'CANCELLED'}
    
    def process_object(self, obj):
        """Process a single mesh object"""
        if obj.type != 'MESH':
            return False
            
        mesh = obj.data
        
        # Ensure object mode (consistent data access)
        if bpy.context.object.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        
        # Set active UV to first layer (index 0) before operation
        if len(mesh.uv_layers) > 0:
            mesh.uv_layers.active_index = 0
        
        # Calculate smooth normals
        smooth_normals = calc_smooth_normals(mesh)
        
        # Ensure mesh has UV layer (required for tangent calculation)
        if len(mesh.uv_layers) == 0:
            mesh.uv_layers.new(name="UVMap")
        
        # Calculate tangent space (TBN matrix)
        mesh.calc_tangents()
        
        # Create/get UV layer
        uv_layer_name = "TEXCOORD1.xy"
        if uv_layer_name in mesh.uv_layers:
            uv_layer = mesh.uv_layers[uv_layer_name]
        else:
            uv_layer = mesh.uv_layers.new(name=uv_layer_name)
        
        # Process each vertex of each face
        for poly in mesh.polygons:
            for loop_idx in range(poly.loop_start, poly.loop_start + poly.loop_total):
                loop = mesh.loops[loop_idx]
                vertex_idx = loop.vertex_index
                
                # Get smooth normal
                normal = smooth_normals[vertex_idx]

                # Build TBN matrix (tangent space to model space transformation)
                tbn_matrix = Matrix((
                    loop.tangent,
                    loop.bitangent,
                    loop.normal
                )).transposed() # Transpose to convert from row vectors to column vectors
                
                # Check if matrix is invertible
                try:
                    # Attempt to calculate inverse matrix
                    tbn_inverse = tbn_matrix.inverted()
                    
                    # Transform normal from model space to tangent space
                    tangent_normal = tbn_inverse @ normal
                    tangent_normal.normalize()
                except ValueError:
                    # Fallback for non-invertible matrix
                    print(f"Warning: TBN matrix for vertex {vertex_idx} is non-invertible, using default normal")
                    
                    tangent_normal = Vector((0, 0, 1))  # Default to Z-axis as normal
                
                # Octahedral projection
                oct_coords = unit_vector_to_octahedron(tangent_normal)
                
                # Set UV coordinates
                u = oct_coords.x
                v = oct_coords.y + 1.0
                uv_layer.data[loop_idx].uv = (u, v)
        
        # Free tangent data
        mesh.free_tangents()
        
        return True
