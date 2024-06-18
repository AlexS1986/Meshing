import numpy as np
import meshio
from scipy.spatial import cKDTree

import numpy as np
import meshio
import os

import utils.alex.process_meshes as mmm 

script_path = os.path.dirname(__file__)
input_mesh_path = os.path.join(script_path,"foam128_corrected_to_box.xdmf")
output_mesh_path = os.path.join(script_path,"translated_foam128.xdmf")

# read pygal output mesh
original_mesh = meshio.read(input_mesh_path)
translate_vector = np.array([ 1.0, 0.0, 0.0 ])



translated_mesh = mmm.translate_mesh(original_mesh, translate_vector)


# Save the merged mesh
meshio.write(output_mesh_path, translated_mesh)


