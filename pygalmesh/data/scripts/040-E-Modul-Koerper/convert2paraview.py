# DOES NOT WORK

import numpy as np
import pyvista as pv
from scipy.spatial import cKDTree
import pygalmesh

import os
script_path = os.path.dirname(__file__)

# Step 1: Read the Tecplot ASCII file
filename = "emodul-ni"
input_filename = filename+".plt"  # Replace with your Tecplot file name
points = []

with open(os.path.join(script_path,input_filename), "r") as file:
    lines = file.readlines()

# Step 2: Extract the data (skip headers)
start_data = False
for line in lines:
    if "ZONE" in line:  # Data starts after the ZONE line
        start_data = True
        continue
    if start_data:
        values = line.strip().split()
        if len(values) == 3:  # Ensure correct number of columns
            points.append([float(values[0]), float(values[1]), float(values[2])])

# Convert to NumPy array
points = np.array(points)

# Step 3: Remove duplicate points
tree = cKDTree(points)
unique_indices = np.unique(tree.query(points, k=1)[1])  # Get unique point indices
unique_points = points[unique_indices]

print(f"Original points: {len(points)}, Unique points: {len(unique_points)}")


# Step 3: Create a PyVista PolyData object
point_cloud = pv.PolyData(unique_points)

# Step 4: Save as a VTK file
output_filename = filename+".vtk"
point_cloud.save(os.path.join(script_path,output_filename))

print(f"Saved VTK file: {output_filename}")


# Load the point cloud
cloud = pv.read(os.path.join(script_path,output_filename))

# Compute the Alpha Shape (adjust alpha value for better fit)
alpha = 0.5  # Smaller = tighter fit, Larger = looser fit
surface = cloud.delaunay_3d(alpha=alpha).extract_surface()

alpha_file_name = filename+"_alphashape"+".vtk"
# Save the Alpha Shape surface as VTK
surface.save(os.path.join(script_path,alpha_file_name))



# try pygalmesh
mesh_size = 200  # Adjust this according to your data

s = pygalmesh.Ball([0, 0, 0], 1.0)

domain = pygalmesh.Domain(unique_points)

pygal_file_name = filename+"_pygal"+".vtk"




# Create the surface mesh
mesh = pygalmesh.generate_surface_mesh(domain, bounding_sphere_radius=200.0, 
                                min_facet_angle=0.0, max_radius_surface_delaunay_ball=0.0,
                                max_facet_distance=0.0, verbose=True, seed=0)


# Save the Alpha Shape surface as VTK
#point_cloud.save(os.path.join(script_path,output_filename))
# Export to VTK format (or other formats ParaView supports, like PLY, STL)
mesh.write(os.path.join(script_path,pygal_file_name))
