import nanomesh
import os
import numpy as np
import matplotlib.pyplot as plt
from skimage.transform import rescale

def plot_image_of_slice_in_subvol(script_path, subvol,coordinate_of_slice, filename):
    plane = subvol.select_plane(x=coordinate_of_slice)


# Save the plane as an image file
    plane_array = np.array(plane.image)
    fig, ax = plt.subplots()
    plane_array = plane_array.astype(np.float32)
    ax.imshow(plane_array, cmap='gray')  # Choose an appropriate colormap
    ax.axis('off')  # Hide axes if not needed

    output_path = os.path.join(script_path, filename)
    fig.savefig(output_path, dpi=300, bbox_inches='tight')

    print(f"Saved image to {output_path}")


# File path
script_path = os.path.dirname(__file__)
#filename = "original_3d_array.npy"
file_path = os.path.join("/data","resources","erik","test_foam_64x64x64.leS")

# Read the data from the file
with open(file_path, 'r') as file:
    # Read all lines and split by spaces to get individual elements
    data = file.read().split()

# Convert data to integers
data = list(map(int, data))


subarray_size = 64
# Convert the list to a NumPy array and reshape to 128x128x128
#vol = np.array(data,dtype=np.uint8).reshape((128, 128, 128))
vol_img = np.array(data,dtype=np.float16).reshape((subarray_size, subarray_size, subarray_size))

voxel_dim = 1.0e-2 #cannot be too small for mesh generation to work properly

#intensity_at_voxels = np.load(file_path)

vol = nanomesh.Image(vol_img)
plot_image_of_slice_in_subvol(script_path,vol,0,"vol_output_plane.png")

# subvol = vol.select_subvolume(
#     zs=(525, 675),
# )
subvol = vol

plot_image_of_slice_in_subvol(script_path, subvol,0,filename="subvol_output_plane.png")

subvol_gauss = subvol.gaussian(sigma=1)
plane = subvol_gauss.select_plane(x=0)
plane.try_all_threshold(figsize=(5, 10))

subvol_seg = subvol_gauss.binary_digitize(threshold='minimum')
subvol_seg = subvol_seg.invert_contrast()
plot_image_of_slice_in_subvol(script_path, subvol_seg,0,filename="subvol_seg_output_plane.png")

mesher = nanomesh.Mesher(subvol_seg)
mesher.generate_contour()
mesh = mesher.tetrahedralize(opts='-pAq')

tet_mesh = mesh.get('tetra')
pv_mesh = tet_mesh.to_pyvista_unstructured_grid()
#trimesh_mesh = triangle_mesh.to_trimesh()
meshio_mesh = tet_mesh.to_meshio()


#mesh.write(os.path.join(script_path,"foam"+str(subarray_size)+".xdmf"))

mesh.write(os.path.join(script_path,"mesh.xdmf"),file_format='gmsh22', binary=False)
mesh.write(os.path.join(script_path,"out.msh"), file_format='gmsh22', binary=False)
#tetr.write('volume_mesh.msh', file_format='gmsh22', binary=False)
