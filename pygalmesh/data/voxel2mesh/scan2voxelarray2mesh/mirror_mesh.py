import numpy as np
import meshio
from scipy.spatial import cKDTree

# def mirror_and_merge(input_mesh_path, output_mesh_path, tolerance=1e-3):
#     # Load the original mesh
#     original_mesh = meshio.read(input_mesh_path)

#     number_vertices = len(original_mesh.points)
    
#     # Mirror along X-axis
#     mirrored_vertices = original_mesh.points * [-1, 1, 1]

#     # Build KD-tree for original vertices
#     tree = cKDTree(original_mesh.points)

#     # Find duplicates within the specified tolerance
#     distances, indices = tree.query(np.concatenate((original_mesh.points,mirrored_vertices)), distance_upper_bound=tolerance)
    
#     # Dictionary to store the pairs (id of removed point in mirrored mesh, id of identical point in original mesh)
#     duplicate_map = {i: idx for i, idx in enumerate(indices) if distances[i] <= tolerance and i != idx}

#     indices_of_duplicate_points = np.array(list(duplicate_map.values()))

#     # Adjust mirrored mesh points and cells
#     mirrored_vertices_filtered = np.array([pt for i, pt in enumerate(mirrored_vertices) if i not in indices_of_duplicate_points])

#     # Adjust the indices in mirrored_mesh.cells to reflect the duplicate removal
#     def adjust_cells(cells):
#         adjusted_cells = cells.copy()
#         for duplicate_point in indices_of_duplicate_points:
#             adjusted_cells[ adjusted_cells != duplicate_point] = duplicate_point + number_vertices
        
#         adjusted_cells = adjusted_cells[:,::-1]
        
#         return np.array(adjusted_cells)

#     # Offset the indices of faces and cells in the mirrored mesh
#     # num_original_points = len(original_mesh.points)
#     mirrored_faces_adjusted = adjust_cells(original_mesh.cells[0].data)
#     mirrored_cells_adjusted = adjust_cells(original_mesh.cells[1].data)

#     # Merge vertices and cells
#     merged_vertices = np.concatenate((original_mesh.points, mirrored_vertices_filtered))
#     merged_faces = np.concatenate((original_mesh.cells[0].data, mirrored_faces_adjusted))
#     merged_cells = np.concatenate((original_mesh.cells[1].data, mirrored_cells_adjusted))

#     # Create a new mesh object
#     merged_mesh = meshio.Mesh(merged_vertices, {"triangle": merged_faces, "tetra": merged_cells})

#     # Save the merged mesh
#     meshio.write(output_mesh_path, merged_mesh)

import numpy as np
import meshio

def mirror_and_merge(input_mesh_path, output_mesh_path):
    # Load the original mesh
    original_mesh = meshio.read(input_mesh_path)
    number_vertices = len(original_mesh.points)

    # Mirror along X-axis
    mirrored_vertices = original_mesh.points * [-1, 1, 1]
    
    
        # Build KD-tree for original vertices
    tree = cKDTree(original_mesh.points)

    # Find duplicates within the specified tolerance
    tolerance = 1.0e-2
    distances, indices = tree.query(np.concatenate((original_mesh.points,mirrored_vertices)), distance_upper_bound=2.0*tolerance)
    
    # Dictionary to store the pairs (id of removed point in mirrored mesh, id of identical point in original mesh)
    duplicate_map = {i: idx for i, idx in enumerate(indices) if distances[i] <= tolerance and i != idx}

    indices_of_duplicate_points = np.array(list(duplicate_map.values()))
    
    # Filter indices_of_duplicate_points based on x-coordinate close to 0
    # tolerance =  3.0e-3  # Define a suitable tolerance for "close to 0"
    filtered_indices = [i for i in indices_of_duplicate_points if np.abs(original_mesh.points[i, 0]) < tolerance]

# Convert filtered indices to a numpy array
    filtered_indices_of_duplicate_points = np.array(filtered_indices)
    
    indices_of_duplicate_points = filtered_indices_of_duplicate_points
    
    point = mirrored_vertices[indices_of_duplicate_points[0]]
    point1 = mirrored_vertices[indices_of_duplicate_points[1]]
    
    #TODO this changes the numbers in merged array since points are removed -> take deletion into account when computing offset
    # mirrored_vertices_filtered = np.array([pt for i,pt in enumerate(mirrored_vertices) if i not in indices_of_duplicate_points])
    # 1. rename all vertices in cells with their names
    # 2. assign offset to all non-duplicate cells (this needs to take missing vertices into account)
    mirrored_vertices_filtered = []
    # mirrored_vertices_filtered = np.array([pt for i,pt in enumerate(mirrored_vertices) if i not in indices_of_duplicate_points])
    offset = np.full(len(original_mesh.points),len(original_mesh.points),dtype=np.uint)
    
    for i, pt in enumerate(mirrored_vertices):
        # index_in_original_array = indices_of_duplicate_points[i]
        if i not in indices_of_duplicate_points:
            mirrored_vertices_filtered.append(pt)
        else:
            offset[i+1:] -= 1
            # offset
            # offset = np.delete(offset,i)
            # original_indices = np.delete(original_indices, np.where(original_indices == indices_of_duplicate_points[i]))

    # mirrored_mesh = original_mesh.copy()
    cells = original_mesh.cells[0].data
        
    # Create a mask to identify elements not in indices_of_duplicate_points
    mask = np.isin(cells, indices_of_duplicate_points, invert=True)
    adjusted_cells = np.where(mask, cells + offset[cells],cells)
    
    
    
    contains_any = np.isin(indices_of_duplicate_points,adjusted_cells)
    
    def adjust_cells(cells):
        adjusted_cells = cells.copy()
        for cell in adjusted_cells:
            # if np.isin(cell,indices_of_duplicate_points).any():
            for i, point in enumerate(cell):
                if point in indices_of_duplicate_points:
                    continue
                else:
                    # tmp = int(offset[point])
                    cell[i] = point + int(offset[point])
                    # a = 1
        
        # for duplicate_point in indices_of_duplicate_points:
        #     adjusted_cells[ adjusted_cells != duplicate_point] = duplicate_point + offset
        
        # adjusted_cells = adjusted_cells[:,::-1]
        
        return np.array(adjusted_cells)
  
    adjusted_faces = adjust_cells(original_mesh.cells[0].data)
    adjusted_cells = adjust_cells(original_mesh.cells[1].data)
    contains_any2 = np.isin(indices_of_duplicate_points,adjusted_faces)
    
    # mirrored_faces_adjusted = 

    # Offset the indices of faces in the mirrored mesh
    # mirrored_mesh = original_mesh.copy()
    # mirrored_mesh.points = mirrored_vertices_filtered
    # mirrored_mesh.cells[0].data += len(original_mesh.points)
    # mirrored_mesh.cells[1].data += len(original_mesh.points)

    # Merge vertices and faces
    merged_vertices = np.concatenate((original_mesh.points, mirrored_vertices_filtered))
    merged_faces = np.concatenate((original_mesh.cells[0].data, adjusted_faces))
    merged_cells = np.concatenate((original_mesh.cells[1].data, adjusted_cells))

    # Create a new mesh object
    merged_mesh = meshio.Mesh(merged_vertices, {"triangle": merged_faces, "tetra": merged_cells})

    # Save the merged mesh
    meshio.write(output_mesh_path, merged_mesh)

# # Example usage
# input_mesh_path = "original_mesh.vtk"
# output_mesh_path = "merged_mesh.vtk"
# mirror_and_merge(input_mesh_path, output_mesh_path)




# Example usage
input_mesh_path = "/data/voxel2mesh/scan2voxelarray2mesh/foam.vtk"
output_mesh_path = "/data/voxel2mesh/scan2voxelarray2mesh/merged_mesh.vtk"
mirror_and_merge(input_mesh_path, output_mesh_path)

