from scipy.spatial import cKDTree, KDTree
import numpy as np
import meshio
import copy

def mirror_and_merge_old(original_mesh, mirror_direction = 0, merging_tolerance = 0.0, mirror_plane_value=0.0):    
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
    
    mirrored_vertices_filtered, offset = remove_vertices_and_compute_offset_mirror(number_points_orignal_mesh, mirrored_vertices, indices_of_duplicate_points)
    
    index_of_tetra_cells = next((index for index, cell in enumerate(original_mesh.cells) if cell.type == "tetra"), None)

    
    # mirrored_faces = apply_offset_to_cells_and_reverse_point_ordering(original_mesh.cells[0].data, offset, indices_of_duplicate_points)
    mirrored_cells = apply_offset_to_cells_and_reverse_point_ordering(original_mesh.cells[index_of_tetra_cells].data, offset, indices_of_duplicate_points)
    
    # Merge vertices and faces
    merged_vertices = np.concatenate((original_mesh.points, mirrored_vertices_filtered))
    # merged_faces = np.concatenate((original_mesh.cells[0].data, mirrored_faces))
    merged_cells = np.concatenate((original_mesh.cells[index_of_tetra_cells].data, mirrored_cells))

    return meshio.Mesh(merged_vertices, {"tetra": merged_cells})

def mirror_and_merge(original_mesh, mirror_direction = 0, merging_tolerance = 0.0, mirror_plane_value=0.0):
    mirrored_mesh = mirror_mesh(original_mesh,mirror_direction=mirror_direction,
                                mirror_plane_value=mirror_plane_value)
    merged_mesh = merge_mesh(mesh1=original_mesh,mesh2=mirrored_mesh, merge_direction=mirror_direction,merging_tolerance=merging_tolerance)
    return merged_mesh


def mirror_mesh(mesh,mirror_direction = 0,mirror_plane_value=0.0):
    mirrored_mesh = copy_mesh(mesh)
    if mirror_direction == 0: # x
        mirror_vector = [-1, 1, 1]
    elif mirror_direction == 1: #y
        mirror_vector = [1, -1, 1]
    elif mirror_direction == 2: #z
        mirror_vector = [1, 1, -1]
    mirrored_mesh.points = mirrored_mesh.points * mirror_vector
    mirrored_mesh.points[:,mirror_direction] += 2.0*mirror_plane_value
    
    points, cells = get_points_and_cells_from_mesh(mirrored_mesh)
    for j in range(len(cells)):
            cells[j] = np.flip(cells[j])
    return mirrored_mesh


    

def merge_mesh(mesh1, mesh2, merge_direction = 0, merging_tolerance = 0.0, merge_plane_value=0.0):     
    number_points_orignal_mesh = len(mesh1.points)
    

    
    # Mirror an axis, e.g. mirror_direction = [-1,1,1] mirrors along X-axis
    mesh2_vertices = mesh2.points 
    
    tolerance = merging_tolerance
    tolerance, indices_of_duplicate_points = find_indices_of_duplicate_points(mesh1, mesh2_vertices, tolerance)
    
    # Filter indices_of_duplicate_points based on x-coordinate close to 0
    indices_of_duplicate_points = filter_duplicate_points_at_mirror_plane(mesh1, tolerance, 
                                                                          indices_of_duplicate_points, 
                                                                          mirror_plane_direction=merge_direction, 
                                                                          mirror_plane_value=merge_plane_value)
    
    # should also work for merging non-equal-meshes
    vertices_to_merge_filtered, offset = remove_vertices_and_compute_offset_mirror(number_points_orignal_mesh, mesh2_vertices, indices_of_duplicate_points)
    
    index_of_tetra_cells = next((index for index, cell in enumerate(mesh2.cells) if cell.type == "tetra"), None)

    
    # mirrored_faces = apply_offset_to_cells_and_reverse_point_ordering(original_mesh.cells[0].data, offset, indices_of_duplicate_points)
    cells_to_merge = apply_offset_to_cells(mesh2.cells[index_of_tetra_cells].data, offset, indices_of_duplicate_points)
    
    # Merge vertices and faces
    merged_vertices = np.concatenate((mesh1.points, vertices_to_merge_filtered))
    # merged_faces = np.concatenate((original_mesh.cells[0].data, mirrored_faces))
    merged_cells = np.concatenate((mesh1.cells[index_of_tetra_cells].data, cells_to_merge))
    return meshio.Mesh(merged_vertices, {"tetra": merged_cells})

def apply_offset_to_cells(cells, offset,indices_of_removed_points):
        adjusted_cells = cells.copy()
        for j in range(len(adjusted_cells)):
            # adjusted_cells[j] = np.flip(adjusted_cells[j]) # reverse the order in each mirrored cell -> so ordering is correct for fem?
            for i, point in enumerate(adjusted_cells[j]):
                if point in indices_of_removed_points:
                    continue
                else:
                    adjusted_cells[j][i] = point + int(offset[point])
        return np.array(adjusted_cells)
    
    
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

def remove_vertices_and_compute_offset_mirror(number_of_vertices_orig_mesh, vertices, indices_of_vertices_to_remove):
    vertices_filtered = []
    # number_of_vertices = len(vertices)
    offset = np.full(number_of_vertices_orig_mesh,number_of_vertices_orig_mesh,dtype=np.uint)
    
    for i, pt in enumerate(vertices):
        if i not in indices_of_vertices_to_remove:
            vertices_filtered.append(pt)
        else:
            offset[i+1:] -= 1
    return vertices_filtered,offset

def remove_vertices_and_compute_offset_2( vertices, indices_of_vertices_to_remove):
    vertices_filtered = []
    number_of_vertices = len(vertices)
    offset = np.full(number_of_vertices,0,dtype=np.int64)
    
    for i, pt in enumerate(vertices):
        if i not in indices_of_vertices_to_remove:
            vertices_filtered.append(pt)
        else:
            offset[i+1:] -= 1
    return vertices_filtered,offset

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

def copy_mesh(mesh):
    points, cells  = get_points_and_cells_from_mesh(mesh)
    return meshio.Mesh(points=copy.deepcopy(points), cells={"tetra": copy.deepcopy(cells)})
    
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







####### Check meshes
def check_for_identical_points(mesh, tolerance):
# Create KDTree
    tree = KDTree(mesh.points)
# Find pairs of points within the given tolerance
    pairs = tree.query_pairs(tolerance)
    has_pairs = bool(pairs)
    return pairs, has_pairs

def print_points(mesh, pairs):
    for pair in pairs:
        idx1, idx2 = pair
        point1, point2 = mesh.points[idx1], mesh.points[idx2]
        print(f"Points {idx1} and {idx2} are within the tolerance")
        print(f"Point {idx1}: {point1}")
        print(f"Point {idx2}: {point2}\n")
        
        
def check_all_points_referenced(mesh):
    points, cells = get_points_and_cells_from_mesh(mesh)
    # Flatten the cells array to get all point indices referenced by cells
    referenced_points = np.unique(cells.flatten())
    all_points = np.arange(points.shape[0])
    
    # Check if all points are referenced
    missing_points = np.setdiff1d(all_points, referenced_points)
    any_missing = len(missing_points) > 0
    
    return missing_points, any_missing

def get_points_and_cells_from_mesh(mesh):
    points = mesh.points
    index_of_tetra_cells = next((index for index, cell in enumerate(mesh.cells) if cell.type == "tetra"), None)
    cells = mesh.cells[index_of_tetra_cells].data
    return points,cells

def check_cell_orientation(mesh, tolerance=1e-12):
    points, cells = get_points_and_cells_from_mesh(mesh)
    incorrect_orientation_cells = []
    zero_volume_cells = []
    
    for i, cell in enumerate(cells):
        p0, p1, p2, p3 = points[cell]

        # Compute the volume of the tetrahedron
        v = np.dot(np.cross(p1 - p0, p2 - p0), p3 - p0)
        
        if v < -tolerance:
            incorrect_orientation_cells.append(i)
        elif abs(v) <= tolerance:
            zero_volume_cells.append(i)
    
    any_incorrect_orientation = len(incorrect_orientation_cells) > 0
    any_zero_volume = len(zero_volume_cells) > 0
    
    return (np.array(incorrect_orientation_cells,dtype=np.int64), any_incorrect_orientation,
            np.array(zero_volume_cells,dtype=np.int64), any_zero_volume)
    
    
def print_mesh_status(missing_points, any_missing, incorrect_orientation_cells, any_incorrect_orientation, zero_volume_cells, any_zero_volume):
    if any_missing:
        print(f"Missing points: {missing_points}")
    else:
        print("All points are referenced by the cells.")

    if any_incorrect_orientation:
        print(f"Cells with incorrect orientation: {incorrect_orientation_cells}")
    else:
        print("All cells have correct orientation.")

    if any_zero_volume:
        print(f"Cells with zero volume: {zero_volume_cells}")
    else:
        print("No cells have zero volume.")
        
        
def remove_invalid_cells(mesh, incorrect_orientation_cells, zero_volume_cells):
    points, cells = get_points_and_cells_from_mesh(mesh)
    # Combine indices of cells to be removed
    cells_to_remove = np.unique(np.concatenate((incorrect_orientation_cells, zero_volume_cells)))
    
    # Create a mask for cells to keep
    mask = np.ones(cells.shape[0], dtype=bool)
    mask[cells_to_remove] = False
    
    # Filter out the invalid cells
    valid_cells = cells[mask]
    
    index_of_tetra_cells = next((index for index, cell in enumerate(mesh.cells) if cell.type == "tetra"), None)
    mesh.cells[index_of_tetra_cells].data = valid_cells
    
    return mesh