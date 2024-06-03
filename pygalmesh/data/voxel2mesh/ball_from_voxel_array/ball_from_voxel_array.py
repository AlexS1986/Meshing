import pygalmesh
import numpy as np
import os

script_path = os.path.dirname(__file__)


x_ = np.linspace(-1.0, 1.0, 50)
y_ = np.linspace(-1.0, 1.0, 50)
z_ = np.linspace(-1.0, 1.0, 50)
x, y, z = np.meshgrid(x_, y_, z_)

vol = np.empty((50, 50, 50), dtype=np.uint8)
idx = x**2 + y**2 + z**2 < 0.5**2
vol[idx] = 1
vol[~idx] = 0

voxel_size = (0.1, 0.1, 0.1)

mesh = pygalmesh.generate_from_array(
    vol, voxel_size, max_facet_distance=0.2, max_cell_circumradius=0.1
)


mesh.write(os.path.join(script_path,"ball.vtk"))