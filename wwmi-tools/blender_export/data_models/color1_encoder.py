import numpy as np
import math

from mathutils import Vector, Matrix

def normalize(v, eps=1e-8):
    return v / (np.linalg.norm(v, axis=1, keepdims=True) + eps)


def compute_tangent_normals(smooth_normals, tangents, bitangent_signs, normals):
    # Normalize everything (important)
    n = normalize(smooth_normals)

    N = normalize(normals)
    T = normalize(tangents)

    B = np.cross(N, T) * bitangent_signs[:, None]
    B = B / (np.linalg.norm(B, axis=1, keepdims=True) + 1e-8)

    # Equivalent to TBN^{-1} @ n
    tx = np.sum(T * n, axis=1)
    ty = np.sum(B * n, axis=1)
    tz = np.sum(N * n, axis=1)

    tangent_normal = np.stack((tx, ty, tz), axis=1)
    tangent_normal = normalize(tangent_normal)

    return tangent_normal


def smooth_normals_angle_weighted(V, F):
    v0 = V[F[:,0]]
    v1 = V[F[:,1]]
    v2 = V[F[:,2]]

    e0 = v1 - v0
    e1 = v2 - v0
    e2 = v2 - v1

    # face normals
    fn = np.cross(e0, e1)
    fn = fn / (np.linalg.norm(fn, axis=1, keepdims=True) + 1e-8)

    # angles at vertices
    def angle(a, b):
        a = a / (np.linalg.norm(a, axis=1, keepdims=True)+1e-8)
        b = b / (np.linalg.norm(b, axis=1, keepdims=True)+1e-8)
        return np.arccos(np.clip(np.sum(a*b, axis=1), -1, 1))

    a0 = angle(v1-v0, v2-v0)
    a1 = angle(v0-v1, v2-v1)
    a2 = angle(v0-v2, v1-v2)

    N = np.zeros_like(V)

    np.add.at(N, F[:,0], fn * a0[:,None])
    np.add.at(N, F[:,1], fn * a1[:,None])
    np.add.at(N, F[:,2], fn * a2[:,None])

    N = N / (np.linalg.norm(N, axis=1, keepdims=True)+1e-8)
    return N


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


def smooth_normals_angle_weighted_vectorized(vertices, faces, eps=1e-6):
    V = vertices
    F = faces

    # Triangle vertices
    v0 = V[F[:,0]]
    v1 = V[F[:,1]]
    v2 = V[F[:,2]]

    # Face normals
    fn = np.cross(v1 - v0, v2 - v0)
    fn_len = np.linalg.norm(fn, axis=1, keepdims=True)
    fn = np.divide(fn, fn_len, out=np.zeros_like(fn), where=fn_len>eps)

    # --- Corner angles ---
    def corner_angle(a, b):
        a_len = np.linalg.norm(a, axis=1)
        b_len = np.linalg.norm(b, axis=1)
        valid = (a_len > eps) & (b_len > eps)

        # Initialize angles to zero
        angle = np.zeros(a.shape[0], dtype=np.float64)

        # Only compute for valid entries
        if np.any(valid):
            a_norm = np.zeros_like(a)
            b_norm = np.zeros_like(b)
            a_norm[valid] = a[valid] / a_len[valid,None]
            b_norm[valid] = b[valid] / b_len[valid,None]
            dot = np.sum(a_norm * b_norm, axis=1)
            dot = np.clip(dot, -1.0, 1.0)
            angle[valid] = np.arccos(dot[valid])
        return angle

    a0 = corner_angle(v1 - v0, v2 - v0)  # angle at v0
    a1 = corner_angle(v0 - v1, v2 - v1)  # angle at v1
    a2 = corner_angle(v0 - v2, v1 - v2)  # angle at v2

    # Accumulate weighted normals
    N = np.zeros_like(V)
    np.add.at(N, F[:,0], fn * a0[:,None])
    np.add.at(N, F[:,1], fn * a1[:,None])
    np.add.at(N, F[:,2], fn * a2[:,None])

    # Normalize per vertex
    lengths = np.linalg.norm(N, axis=1, keepdims=True)
    N = np.divide(N, lengths, out=np.zeros_like(N), where=lengths>eps)
    return N


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
