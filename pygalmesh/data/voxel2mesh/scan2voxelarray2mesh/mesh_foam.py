import numpy as np
import pygalmesh
import os

# File path
file_path = '/data/resources/hypo_smoothed_128.dat'
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

mesh = pygalmesh.generate_from_array(
    sub_vol, voxel_size, max_cell_circumradius=1.0*voxel_dim, #max_facet_distance=0.1*voxel_dim
)

mesh.write(os.path.join(script_path,"foam.vtk"))
