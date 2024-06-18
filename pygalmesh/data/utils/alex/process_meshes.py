from scipy.spatial import cKDTree
import numpy as np
import meshio

def mirror_and_merge(original_mesh, mirror_direction = 0, merging_tolerance = 0.0, mirror_plane_value=0.0):    
    number_points_orignal_mesh = len(original_mesh.points)
    
    if mirror_direction == 0: # x
        mirror_vector = [-1, 1, 1]
    elif mirror_direction == 1: #y
        mirror_vector = [1, -1, 1]
    elif mirror_direction == 2: #z
        mirror_vector = [1, 1, -1]
    

    # Mirror an axis, e.g. mirror_direction = [-1,1,1] mirrors along X-axis
    mirrored_vertices = original_mesh.points * mirror_vector
    mirrored_vertices[:,mirror_direction] += 2.0*mirror_plane_value
    
    tolerance = merging_tolerance
    tolerance, indices_of_duplicate_points = find_indices_of_duplicate_points(original_mesh, mirrored_vertices, tolerance)
    
    # Filter indices_of_duplicate_points based on x-coordinate close to 0
    indices_of_duplicate_points = filter_duplicate_points_at_mirror_plane(original_mesh, tolerance, 
                                                                          indices_of_duplicate_points, 
                                                                          mirror_plane_direction=mirror_direction, 
                                                                          mirror_plane_value=mirror_plane_value)
    
    mirrored_vertices_filtered, offset = remove_duplicate_points_and_compute_offset(number_points_orignal_mesh, mirrored_vertices, indices_of_duplicate_points)
    
    index_of_tetra_cells = next((index for index, cell in enumerate(original_mesh.cells) if cell.type == "tetra"), None)

    
    # mirrored_faces = apply_offset_to_cells_and_reverse_point_ordering(original_mesh.cells[0].data, offset, indices_of_duplicate_points)
    mirrored_cells = apply_offset_to_cells_and_reverse_point_ordering(original_mesh.cells[index_of_tetra_cells].data, offset, indices_of_duplicate_points)
    
    # Merge vertices and faces
    merged_vertices = np.concatenate((original_mesh.points, mirrored_vertices_filtered))
    # merged_faces = np.concatenate((original_mesh.cells[0].data, mirrored_faces))
    merged_cells = np.concatenate((original_mesh.cells[index_of_tetra_cells].data, mirrored_cells))

    return merged_vertices, merged_cells
   
    
    
def apply_offset_to_cells_and_reverse_point_ordering(cells, offset,indices_of_duplicate_points):
        adjusted_cells = cells.copy()
        for j in range(len(adjusted_cells)):
            adjusted_cells[j] = np.flip(adjusted_cells[j]) # reverse the order in each mirrored cell -> so ordering is correct for fem?
            for i, point in enumerate(adjusted_cells[j]):
                if point in indices_of_duplicate_points:
                    continue
                else:
                    adjusted_cells[j][i] = point + int(offset[point])
        return np.array(adjusted_cells)

def remove_duplicate_points_and_compute_offset(number_points_orignal_mesh, mirrored_vertices, indices_of_duplicate_points):
    mirrored_vertices_filtered = []
    offset = np.full(number_points_orignal_mesh,number_points_orignal_mesh,dtype=np.uint)
    
    for i, pt in enumerate(mirrored_vertices):
        if i not in indices_of_duplicate_points:
            mirrored_vertices_filtered.append(pt)
        else:
            offset[i+1:] -= 1
    return mirrored_vertices_filtered,offset

def filter_duplicate_points_at_mirror_plane(original_mesh, tolerance, indices_of_duplicate_points, mirror_plane_direction: int = 0, mirror_plane_value: float = 0.0):
    filtered_indices = [i for i in indices_of_duplicate_points if np.isclose(original_mesh.points[i, mirror_plane_direction], mirror_plane_value, atol=tolerance)]
    filtered_indices_of_duplicate_points = np.array(filtered_indices)
    indices_of_duplicate_points = filtered_indices_of_duplicate_points
    return indices_of_duplicate_points

def find_indices_of_duplicate_points(original_mesh, mirrored_vertices, tolerance):
    tree = cKDTree(original_mesh.points)
    # Find duplicates within the specified tolerance
    distances, indices = tree.query(np.concatenate((original_mesh.points,mirrored_vertices)), distance_upper_bound=2.0*tolerance)
    
    # Dictionary to store the pairs (id of removed point in mirrored mesh, id of identical point in original mesh)
    duplicate_map = {i: idx for i, idx in enumerate(indices) if distances[i] <= tolerance and i != idx}

    indices_of_duplicate_points = np.array(list(duplicate_map.values()))
    return tolerance,indices_of_duplicate_points



def scale_mesh(original_mesh, scal):
    points = original_mesh.points * scal
    index_of_tetra_cells = next((index for index, cell in enumerate(original_mesh.cells) if cell.type == "tetra"), None)
    cells = original_mesh.cells[index_of_tetra_cells].data

# Create a new mesh object from vertices and cells
    scaled_mesh = meshio.Mesh(points=points, cells={"tetra": cells})
    return scaled_mesh

def translate_mesh(original_mesh, translate_vector):
    points = original_mesh.points
    points = points + translate_vector

    index_of_tetra_cells = next((index for index, cell in enumerate(original_mesh.cells) if cell.type == "tetra"), None)
    cells = original_mesh.cells[index_of_tetra_cells].data

# Create a new mesh object from vertices and cells
    translated_mesh = meshio.Mesh(points=points, cells={"tetra": cells})
    return translated_mesh


def correct_mesh_to_box(points, xmin, xmax, ymin, ymax, zmin, zmax, tolerance):
    # Correct first column (x values)
    points[:, 0] = np.where(np.abs(points[:, 0] - xmin) <= tolerance, xmin, points[:, 0])
    points[:, 0] = np.where(np.abs(points[:, 0] - xmax) <= tolerance, xmax, points[:, 0])
    
    # Correct second column (y values)
    points[:, 1] = np.where(np.abs(points[:, 1] - ymin) <= tolerance, ymin, points[:, 1])
    points[:, 1] = np.where(np.abs(points[:, 1] - ymax) <= tolerance, ymax, points[:, 1])
    
    # Correct third column (z values)
    points[:, 2] = np.where(np.abs(points[:, 2] - zmin) <= tolerance, zmin, points[:, 2])
    points[:, 2] = np.where(np.abs(points[:, 2] - zmax) <= tolerance, zmax, points[:, 2])
    
    return points