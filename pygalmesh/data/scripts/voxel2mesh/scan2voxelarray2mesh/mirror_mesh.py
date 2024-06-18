import numpy as np
import meshio
from scipy.spatial import cKDTree

import numpy as np
import meshio
import os

import utils.alex.process_meshes as mmm 

script_path = os.path.dirname(__file__)
input_mesh_path = os.path.join(script_path,"foam128_corrected_to_box.xdmf")
output_mesh_path = os.path.join(script_path,"mirrored_hypo_test_128.xdmf")

# read pygal output mesh
original_mesh = meshio.read(input_mesh_path)

max_coordinates =  np.max(original_mesh.points,axis=0)
mirror_dir_index = 1

mirrored_merged_vertices,  mirrored_merged_cells = mmm.mirror_and_merge(
    original_mesh, mirror_direction =  mirror_dir_index, mirror_plane_value=max_coordinates[mirror_dir_index], merging_tolerance=3.0e-2)

# Create a new mesh object from vertices and cells
mirrored_mesh = meshio.Mesh(mirrored_merged_vertices, {"tetra": mirrored_merged_cells})

# Save the merged mesh
meshio.write(output_mesh_path, mirrored_mesh)


