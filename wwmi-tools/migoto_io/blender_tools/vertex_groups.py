import bpy
import re

from textwrap import dedent

from ..blender_interface.objects import *


def remove_all_vertex_groups(context, obj):
    if obj is None:
        return
    if obj.type != 'MESH':
        return
    for x in obj.vertex_groups:
        obj.vertex_groups.remove(x)


def remove_unused_vertex_groups(context, obj):
    # take from: https://blenderartists.org/t/batch-delete-vertex-groups-script/449881/23#:~:text=10%20MONTHS%20LATER-,AdenFlorian,-Jun%202021
    
    with OpenObject(context, obj) as obj:

        vgroup_used = {i: False for i, k in enumerate(obj.vertex_groups)}

        for v in obj.data.vertices:
            for g in v.groups:
                if g.weight > 0.0:
                    vgroup_used[g.group] = True
        
        for i, used in sorted(vgroup_used.items(), reverse=True):
            if not used:
                obj.vertex_groups.remove(obj.vertex_groups[i])


vg_id_pattern = re.compile(r"^\s*(\d+).*")

def fill_gaps_in_vertex_groups(context, obj, internal_call = False):
    """
    Fills empty spots in list of VGs with conventional names (ones that start with numeric IDs)
    Example: [0, 3, 4, 6] transforms to [0, 1, 2, 3, 4, 5, 6]
    """

    with OpenObject(context, obj) as obj:

        vg_ids = [vg_id_pattern.findall(vg.name) for vg in obj.vertex_groups]
        vg_ids = [int(vg_id[0]) if vg_id else -1 for vg_id in vg_ids]
        
        if len(vg_ids) == 0:
            return

        vg_count = max(vg_ids) + 1

        if vg_count == 0:
            return
        
        # Limit the list of existing IDs to filling range
        vg_ids = vg_ids[:min(len(vg_ids), vg_count)]

        # Ensure abscence of VGs without numeric IDs sharing indices with missing IDs we're about to add
        if -1 in vg_ids:
            if internal_call:
                raise ValueError(dedent(f"""
                    Vertex Group names of object `{obj.name.removeprefix('TEMP_')}` are ambigous!
                    VG `{obj.vertex_groups[vg_ids.index(-1)].name}` is located among VGs with numeric IDs!
                    Make sure that either all or none VG names start with numeric IDs.
                    Alternatively, disable `Add Missing Vertex Groups` in `Advanced` tab.
                """))
            else:
                raise ValueError(dedent(f"""
                    Vertex Group names of object `{obj.name}` are ambigous!
                    VG `{obj.vertex_groups[vg_ids.index(-1)].name}` is located among VGs with numeric IDs!
                    Make sure that either all or none VG names start with numeric IDs.
                """))

        expected_vg_ids = set([str(vg_id) for vg_id in range(vg_count)])
        missing_vg_ids = expected_vg_ids - set(map(str, vg_ids))
    
        for vg_id in missing_vg_ids:
            obj.vertex_groups.new(name=vg_id)

        bpy.ops.object.vertex_group_sort()


def merge_vertex_groups(context, obj):
    # Author: SilentNightSound#7430

    # Combines vertex groups with the same prefix into one, a fast alternative to the Vertex Weight Mix that works for multiple groups
    # You will likely want to use blender_fill_vg_gaps.txt after this to fill in any gaps caused by merging groups together
    # Runs the merge on ALL vertex groups in the selected object(s)

    with OpenObject(context, obj) as obj:

        vg_names = [vg.name.split(".")[0] for vg in obj.vertex_groups]

        if not vg_names:
            raise ValueError('No vertex groups found, make sure that selected object has vertex groups!')

        for vg_name in vg_names:

            relevant = [x.name for x in obj.vertex_groups if x.name.split(".")[0] == f"{vg_name}"]

            if relevant:

                vgroup = obj.vertex_groups.new(name=f"x{vg_name}")
                    
                for vert_id, vert in enumerate(obj.data.vertices):
                    available_groups = [v_group_elem.group for v_group_elem in vert.groups]
                    
                    combined = 0
                    for v in relevant:
                        if obj.vertex_groups[v].index in available_groups:
                            combined += obj.vertex_groups[v].weight(vert_id)

                    if combined > 0:
                        vgroup.add([vert_id], combined ,'ADD')
                        
                for vg in [x for x in obj.vertex_groups if x.name.split(".")[0] == f"{vg_name}"]:
                    obj.vertex_groups.remove(vg)

                for vg in obj.vertex_groups:
                    if vg.name[0].lower() == "x":
                        vg.name = vg.name[1:]
                            
        bpy.ops.object.vertex_group_sort()
