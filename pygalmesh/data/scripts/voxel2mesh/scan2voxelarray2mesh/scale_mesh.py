import numpy as np
import meshio
from scipy.spatial import cKDTree

import numpy as np
import meshio
import os

import utils.alex.process_meshes as mmm 

script_path = os.path.dirname(__file__)
input_mesh_path = os.path.join(script_path,"foam128_corrected_to_box.xdmf")
output_mesh_path = os.path.join(script_path,"scaled_foam128.xdmf")

# read pygal output mesh
original_mesh = meshio.read(input_mesh_path)
scal = 1.0/2.0

scaled_mesh = mmm.scale_mesh(original_mesh, scal)

# Save the merged mesh
meshio.write(output_mesh_path, scaled_mesh)


