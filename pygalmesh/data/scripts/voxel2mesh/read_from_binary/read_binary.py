import numpy as np
import os
import pygalmesh


file_path = '/data/resources/hypo_test_128.raw'

script_path = os.path.dirname(__file__)

vol = np.fromfile(file_path, dtype=np.uint8).reshape((128, 128, 128),order='F') # ordering needs to be changed for raw
# vol = np.array(vol,dtype=np.uint8)
max = np.max(vol)
min = np.min(vol)

# flat_array = vol.flatten()
# with open(os.path.join(script_path,'output_file.dat'), 'w') as file:
#         for i in range(0, len(flat_array), 128):
#             line = ' '.join(map(str, flat_array[i:i+128]))
#             file.write(line + '\n')


# # File path
# file_path = '/data/resources/hypo_test_128.dat'
# script_path = os.path.dirname(__file__)

# # Read the data from the file
# with open(file_path, 'r') as file:
#     # Read all lines and split by spaces to get individual elements
#     data = file.read().split()

# # Convert data to integers
# data = list(map(int, data))

# # Convert the list to a NumPy array and reshape to 128x128x128
# vol_from_text = np.array(data,dtype=np.uint8).reshape((128, 128, 128))

# mask = vol != vol_from_text

# indices_where_differ = np.where(mask)[0]




# equal = np.array_equal(vol,vol_from_text)

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

print("hi")