import numpy as np
import pygalmesh
import os

# File path
file_path = '/data/resources/hypo_mirrored_128.dat'
voxel_number = 128
script_path = os.path.dirname(__file__)

# Read the data from the file
with open(file_path, 'r') as file:
    # Read all lines and split by spaces to get individual elements
    data = file.read().split()

# Convert data to integersvscode-remote://ssh-remote%2Blcluster14.hrz.tu-darmstadt.de/home/as12vapa/jobs/job_Keff
data = list(map(int, data))


# Convert the list to a NumPy array and reshape to 128x128x128
vol = np.array(data,dtype=np.uint8).reshape((voxel_number, voxel_number, 2*voxel_number))


voxel_dim = 1.0e-2 #cannot be too small for mesh generation to work properly
voxel_size = (voxel_dim, voxel_dim, voxel_dim)


mesh = pygalmesh.generate_from_array(
    vol, voxel_size, max_cell_circumradius=1.0*voxel_dim, #max_facet_distance=0.1*voxel_dim
)

mesh.write(os.path.join(script_path,"foam_mirrored" + str(voxel_number) + ".vtk"))
