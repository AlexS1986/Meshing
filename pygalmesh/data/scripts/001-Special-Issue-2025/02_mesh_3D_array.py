import os
import numpy as np
import matplotlib.pyplot as plt
import nanomesh


def plot_image_of_slice_in_subvol(script_path, subvol, z_coordinate_of_slice, filename):
    """
    Save a 2D slice image from a nanomesh volume to file.
    """
    plane = subvol.select_plane(x=z_coordinate_of_slice)
    plane_array = np.array(plane.image).astype(np.float32)

    fig, ax = plt.subplots()
    ax.imshow(plane_array, cmap='gray')
    ax.axis('off')

    output_path = os.path.join(script_path, filename)
    fig.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close(fig)

    print(f"✅ Saved image to {output_path}")


if __name__ == "__main__":
    # Paths
    script_path = os.path.dirname(__file__)
    
    specimen_name = "JM-25-26_segmented"
    input_folder = os.path.join(script_path, specimen_name, specimen_name + "_3D")
    
    input_filename = specimen_name+"_3D.npy"
    input_path = os.path.join(input_folder, input_filename)

    # Load 3D volume
    intensity_at_voxels = np.load(input_path)
    vol = nanomesh.Image(intensity_at_voxels)

    # Visualize initial slice
    plot_image_of_slice_in_subvol(script_path, vol, z_coordinate_of_slice=0, filename="vol_output_plane.png")

    # Extract a subvolume
    subvol = vol.select_subvolume(zs=(000, 300))
    plot_image_of_slice_in_subvol(script_path, subvol, z_coordinate_of_slice=0, filename="subvol_output_plane.png")

    # # Smooth and threshold
    subvol_gauss = subvol.gaussian(sigma=1)
    subvol_seg = subvol_gauss.binary_digitize(threshold='minimum').invert_contrast()
    plot_image_of_slice_in_subvol(script_path, subvol_seg, z_coordinate_of_slice=0, filename="subvol_seg_output_plane.png")

    # Generate mesh
    mesher = nanomesh.Mesher(subvol_seg)
    mesher.generate_contour()
    mesh = mesher.tetrahedralize(opts='-pq')

    # Save mesh in various formats
    mesh.write(os.path.join(script_path, "mesh.xdmf"))
    mesh.write(os.path.join(script_path, "out.msh"), file_format='gmsh22', binary=False)
    print("✅ Mesh saved as 'mesh.xdmf' and 'out.msh'")