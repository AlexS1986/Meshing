import os 
import numpy as np

script_path = os.path.dirname(__file__)
filename = "segmented_3d_array.npy"

intensity_at_voxels = np.load(os.path.join(script_path,filename))

a=1