import numpy as np
import meshio
from scipy.spatial import cKDTree

import numpy as np
import meshio
import os

import utils.alex.process_meshes as mmm 

script_path = os.path.dirname(__file__)
input_mesh_path = os.path.join(script_path,"foam128_corrected_to_box.xdmf")
output_mesh_path = os.path.join(script_path,"medium_pores.xdmf")
# input_mesh_path = os.path.join(script_path,"medium_pores.xdmf")
# output_mesh_path = os.path.join(script_path,"fine_pores.xdmf")

merging_tolerance = 1.0e-2

# read pygal output mesh
original_mesh = meshio.read(input_mesh_path)

min_coordinates =  np.min(original_mesh.points,axis=0)
mirror_dir_index = 0

mirrored_merged_vertices,  mirrored_merged_cells = mmm.mirror_and_merge(
    original_mesh, mirror_direction =  mirror_dir_index, mirror_plane_value=min_coordinates[mirror_dir_index], merging_tolerance=merging_tolerance)

# Create a new mesh object from vertices and cells
mesh = meshio.Mesh(mirrored_merged_vertices, {"tetra": mirrored_merged_cells})

# translate to xmin = 0
min_coordinates =  np.min(mesh.points,axis=0)
mesh = mmm.translate_mesh(mesh,np.array([-min_coordinates[0], 0, 0]))
# min_coordinates =  np.min(mesh.points,axis=0)






# 2. mirror at ymax
min_coordinates =  np.min(mesh.points,axis=0)
mirror_dir_index = 1

mirrored_merged_vertices,  mirrored_merged_cells = mmm.mirror_and_merge(
    mesh, mirror_direction =  mirror_dir_index, mirror_plane_value=min_coordinates[mirror_dir_index], merging_tolerance=merging_tolerance)

mesh = meshio.Mesh(mirrored_merged_vertices, {"tetra": mirrored_merged_cells})
min_coordinates =  np.min(mesh.points,axis=0)
mesh = mmm.translate_mesh(mesh,np.array([0, -min_coordinates[0], 0]))


# 3. mirror at zmax
min_coordinates =  np.min(mesh.points,axis=0)
mirror_dir_index = 2

mirrored_merged_vertices,  mirrored_merged_cells = mmm.mirror_and_merge(
    mesh, mirror_direction =  mirror_dir_index, mirror_plane_value=min_coordinates[mirror_dir_index], merging_tolerance=merging_tolerance)

mesh = meshio.Mesh(mirrored_merged_vertices, {"tetra": mirrored_merged_cells})
min_coordinates =  np.min(mesh.points,axis=0)
mesh = mmm.translate_mesh(mesh,np.array([0,0, -min_coordinates[0]]))


# 4. mirror at xmax again
min_coordinates =  np.max(mesh.points,axis=0)
mirror_dir_index = 0

mirrored_merged_vertices,  mirrored_merged_cells = mmm.mirror_and_merge(
    mesh, mirror_direction =  mirror_dir_index, mirror_plane_value=min_coordinates[mirror_dir_index], merging_tolerance=merging_tolerance)

mesh = meshio.Mesh(mirrored_merged_vertices, {"tetra": mirrored_merged_cells})
min_coordinates =  np.min(mesh.points,axis=0)
mesh = mmm.translate_mesh(mesh,np.array([-min_coordinates[0], 0, 0]))


# 5. scale down to size of original mesh
mesh = mmm.scale_mesh(mesh,scal=1.0 / 2.0)


# Save the merged mesh
meshio.write(output_mesh_path, mesh)



