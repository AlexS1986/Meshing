import numpy as np
import meshio
from scipy.spatial import cKDTree

import numpy as np
import meshio
import os

import utils.alex.process_meshes as mmm 

script_path = os.path.dirname(__file__)
input_mesh_path = os.path.join(script_path,"medium_pores.xdmf")
output_mesh_path = os.path.join(script_path,"medium_pores_original_scale.xdmf")

# read pygal output mesh
original_mesh = meshio.read(input_mesh_path)
scal = 10.0**(-4)*2.0

scaled_mesh = mmm.scale_mesh(original_mesh, scal)

# Save the merged mesh
meshio.write(output_mesh_path, scaled_mesh)


