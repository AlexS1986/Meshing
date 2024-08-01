import numpy as np
import pygalmesh
import os
import numpy as np
import meshio
from scipy.spatial import KDTree

import utils.alex.process_meshes as mmm 

###############################
## 1. mesh with pygalmesh    ##
###############################

# File path
file_path = '/data/resources/hypo_test_128.dat'
script_path = os.path.dirname(__file__)

# Read the data from the file
with open(file_path, 'r') as file:
    # Read all lines and split by spaces to get individual elements
    data = file.read().split()

# Convert data to integers
data = list(map(int, data))

# Convert the list to a NumPy array and reshape to 128x128x128
vol = np.array(data,dtype=np.uint8).reshape((128, 128, 128))

voxel_dim = 1.0e-2 #cannot be too small for mesh generation to work properly
voxel_size = (voxel_dim, voxel_dim, voxel_dim)

# Define the starting indices for the subarray
start_x, start_y, start_z = 0, 0, 0  # You can change these to any valid starting point

# Define the size of the subarray
subarray_size = 128

# Extract the subarray
sub_vol = vol[start_x:start_x+subarray_size, start_y:start_y+subarray_size, start_z:start_z+subarray_size]

max_element_size = 2.0*voxel_dim
mesh = pygalmesh.generate_from_array(
    sub_vol, voxel_size, max_cell_circumradius=max_element_size, max_facet_distance=0.5*voxel_dim
)

mesh.write(os.path.join(script_path,"foam"+str(subarray_size)+".xdmf"))


###############################
## 2. stretch to box         ##
###############################

script_path = os.path.dirname(__file__)
input_mesh_path = os.path.join(script_path,"foam"+str(subarray_size)+".xdmf")
output_mesh_path = os.path.join(script_path,"foam128_corrected_to_box.xdmf")
output_mesh_path = os.path.join(script_path,"foam"+str(subarray_size)+"_corrected_to_box.xdmf")

voxel_num_x = subarray_size
voxel_num_y = voxel_num_x
voxel_num_z = voxel_num_x

voxel_size_x = voxel_dim
voxel_size_y = voxel_size_x
voxel_size_z = voxel_size_x

# read pygal output mesh
original_mesh = meshio.read(input_mesh_path)
points = original_mesh.points

max_displacement_of_points = 0.8*max_element_size

# Get the minimum values in each column
min_values_before = np.min(points, axis=0)
# Get the maximum values in each column
max_values_before = np.max(points, axis=0)

xmin = min_values_before[0]
xmax = max_values_before[0]
ymin = min_values_before[1]
ymax = max_values_before[1]
zmin = min_values_before[2]
zmax = max_values_before[2]

points = mmm.correct_mesh_to_box(points,xmin,xmax,ymin,ymax,zmin,zmax,tolerance=max_displacement_of_points)

# Get the minimum values in each column
min_values_after = np.min(points, axis=0)
# Get the maximum values in each column
max_values_after = np.max(points, axis=0)

tetra_cells = original_mesh.cells[1].data
# Create a new mesh object from vertices and cells
corrected_mesh = meshio.Mesh(points, {"tetra": tetra_cells})

# Save the stretched mesh
meshio.write(output_mesh_path,corrected_mesh)



#########################################################
## 3. generate meshes by mirroring and merging         ##
#########################################################

###################################################
## 3a) generare COARSE mesh by mirroring once    ##
###################################################


script_path = os.path.dirname(__file__)
input_mesh_path = os.path.join(script_path,"foam128_corrected_to_box.xdmf")
# input_mesh_path = os.path.join(script_path,"foam128.xdmf")
merging_tolerance = 0.019*max_element_size


output_mesh_path_coarse = os.path.join(script_path,"coarse_pores.xdmf")
output_mesh_path_medium = os.path.join(script_path,"medium_pores.xdmf")
output_mesh_path_fine = os.path.join(script_path,"fine_pores.xdmf")


# read pygal output mesh
mesh = meshio.read(input_mesh_path)

tolerance_for_points_to_be_considered_identical = 0.019*max_element_size  # tolerance within which points are considered identical
##### check mesh
pairs, has_pairs = mmm.check_for_identical_points(mesh,tolerance_for_points_to_be_considered_identical)
missing_points, any_missing = mmm.check_all_points_referenced(mesh) # missing is not bad
incorrect_orientation_cells, any_incorrect_orientation, zero_volume_cells, any_zero_volume = mmm.check_cell_orientation(mesh,tolerance=0.001*max_element_size**3) # zero volume or incorrect orientation breaks the mesh!
mmm.print_mesh_status(missing_points, any_missing, incorrect_orientation_cells, any_incorrect_orientation, zero_volume_cells, any_zero_volume)
# correct_mesh
mesh = mmm.remove_invalid_cells(mesh,incorrect_orientation_cells,zero_volume_cells)


mirror_plane_values =  np.min(mesh.points,axis=0)
mirror_dir_index = 0

# 1. mirror in x-direction
mesh = mmm.mirror_and_merge_old(mesh,mirror_direction=0,merging_tolerance=merging_tolerance,
                                mirror_plane_value=mirror_plane_values[mirror_dir_index])
pairs, has_pairs = mmm.check_for_identical_points(mesh,tolerance_for_points_to_be_considered_identical)

# translate to origin
minimum_coordinates_new_mesh =  np.min(mesh.points,axis=0)
vector_to_origin = np.array([-minimum_coordinates_new_mesh[0],-minimum_coordinates_new_mesh[1],-minimum_coordinates_new_mesh[2]])
mesh = mmm.translate_mesh(mesh,vector_to_origin)
meshio.write(output_mesh_path_coarse, mesh)

#################################
## 3b) generare MEDIUM mesh    ##
#################################

# 2. mirror in z-direction
mirror_plane_values =  np.min(mesh.points,axis=0)
mirror_dir_index = 2

mesh = mmm.mirror_and_merge_old(
    mesh, mirror_direction =  mirror_dir_index, mirror_plane_value=mirror_plane_values[mirror_dir_index], 
    merging_tolerance=merging_tolerance)

# translate to origin
minimum_coordinates_new_mesh =  np.min(mesh.points,axis=0)
vector_to_origin = np.array([-minimum_coordinates_new_mesh[0],-minimum_coordinates_new_mesh[1],-minimum_coordinates_new_mesh[2]])
mesh = mmm.translate_mesh(mesh,vector_to_origin)

# 3. mirror in x-direction again
mirror_plane_values =  np.min(mesh.points,axis=0)
mirror_dir_index = 0

mesh = mmm.mirror_and_merge_old(
    mesh, mirror_direction =  mirror_dir_index, mirror_plane_value=mirror_plane_values[mirror_dir_index], 
    merging_tolerance=merging_tolerance)

# translate to origin
minimum_coordinates_new_mesh =  np.min(mesh.points,axis=0)
vector_to_origin = np.array([-minimum_coordinates_new_mesh[0],-minimum_coordinates_new_mesh[1],-minimum_coordinates_new_mesh[2]])
mesh = mmm.translate_mesh(mesh,vector_to_origin)
mesh_copy = mmm.copy_mesh(mesh)


# 4. mirror in y-direction min
mirror_plane_values =  np.min(mesh.points,axis=0)
mirror_dir_index = 1


mesh= mmm.mirror_and_merge_old(
    mesh, mirror_direction =  mirror_dir_index, mirror_plane_value=mirror_plane_values[mirror_dir_index], 
    merging_tolerance=merging_tolerance)

# translate to origin
minimum_coordinates_new_mesh =  np.min(mesh.points,axis=0)
vector_to_origin = np.array([-minimum_coordinates_new_mesh[0],-minimum_coordinates_new_mesh[1],-minimum_coordinates_new_mesh[2]])
mesh = mmm.translate_mesh(mesh,vector_to_origin)

mesh = mmm.scale_mesh(mesh,scal=1.0/2.0)

# Save the merged mesh
meshio.write(output_mesh_path_medium, mesh)


###################################################
## 3c) generare FINE mesh                        ##
###################################################

# 1. mirror in z-direction
mirror_plane_values =  np.min(mesh.points,axis=0)
mirror_dir_index = 2

mesh = mmm.mirror_and_merge_old(
    mesh, mirror_direction =  mirror_dir_index, mirror_plane_value=mirror_plane_values[mirror_dir_index], 
    merging_tolerance=merging_tolerance)

# translate to origin
minimum_coordinates_new_mesh =  np.min(mesh.points,axis=0)
vector_to_origin = np.array([-minimum_coordinates_new_mesh[0],-minimum_coordinates_new_mesh[1],-minimum_coordinates_new_mesh[2]])
mesh = mmm.translate_mesh(mesh,vector_to_origin)


# 2. mirror in y-direction
mirror_plane_values =  np.min(mesh.points,axis=0)
mirror_dir_index = 1

mesh = mmm.mirror_and_merge_old(
    mesh, mirror_direction =  mirror_dir_index, mirror_plane_value=mirror_plane_values[mirror_dir_index], 
    merging_tolerance=merging_tolerance)

# translate to origin
minimum_coordinates_new_mesh =  np.min(mesh.points,axis=0)
vector_to_origin = np.array([-minimum_coordinates_new_mesh[0],-minimum_coordinates_new_mesh[1],-minimum_coordinates_new_mesh[2]])
mesh = mmm.translate_mesh(mesh,vector_to_origin)


# 3. mirror in x-direction
mirror_plane_values =  np.min(mesh.points,axis=0)
mirror_dir_index = 0

mesh = mmm.mirror_and_merge_old(
    mesh, mirror_direction =  mirror_dir_index, mirror_plane_value=mirror_plane_values[mirror_dir_index], 
    merging_tolerance=merging_tolerance)

# translate to origin
minimum_coordinates_new_mesh =  np.min(mesh.points,axis=0)
vector_to_origin = np.array([-minimum_coordinates_new_mesh[0],-minimum_coordinates_new_mesh[1],-minimum_coordinates_new_mesh[2]])
mesh = mmm.translate_mesh(mesh,vector_to_origin)

mesh = mmm.scale_mesh(mesh,scal=1.0/2.0)

# Save the merged mesh
meshio.write(output_mesh_path_fine, mesh)





