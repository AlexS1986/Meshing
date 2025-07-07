# run this first on terminal:
# Xvfb :99 -screen 0 1024x768x24 &
# export DISPLAY=:99


import numpy as np
import pyvista as pv
from scipy.spatial import cKDTree
import open3d as o3d
import os

# Change this threshold as needed
DISTANCE_THRESHOLD = 70000.0

script_path = os.path.dirname(__file__)

# Step 1: Read the Tecplot ASCII file
filename = "emodul"
input_filename = filename + ".plt"
points = []

with open(os.path.join(script_path, input_filename), "r") as file:
    lines = file.readlines()

# Step 2: Extract the data (skip headers)
start_data = False
for line in lines:
    if "ZONE" in line:
        start_data = True
        continue
    if start_data:
        values = line.strip().split()
        if len(values) == 3:
            points.append([float(values[0]), float(values[1]), float(values[2])])

points = np.array(points)

# Step 3: Remove duplicate points
tree = cKDTree(points)
unique_indices = np.unique(tree.query(points, k=1)[1])
unique_points = points[unique_indices]

# Step 4: Compute distances from origin and filter by threshold
distances = np.linalg.norm(unique_points, axis=1)
mask = distances <= DISTANCE_THRESHOLD
filtered_points = unique_points[mask]
filtered_distances = distances[mask]

print(f"Original points: {len(points)}, Unique points: {len(unique_points)}, Filtered points: {len(filtered_points)}")

# Step 5: Compute normals
normals = filtered_points / np.linalg.norm(filtered_points, axis=1)[:, np.newaxis]

# Open3D point cloud creation
pcd = o3d.geometry.PointCloud()
pcd.points = o3d.utility.Vector3dVector(filtered_points[:, :3])
pcd.normals = o3d.utility.Vector3dVector(normals[:, :3])

# PyVista point cloud
point_cloud = pv.PolyData(filtered_points)
point_cloud["DistanceFromOrigin"] = filtered_distances

# Visualize and save screenshot
plotter = pv.Plotter(off_screen=True)
plotter.add_points(point_cloud, render_points_as_spheres=True)
output_image_filename = filename + "_point_cloud.png"
plotter.screenshot(os.path.join(script_path, output_image_filename))
print(f"Point cloud visualization saved as {output_image_filename}")

# BPA Meshing
distances = pcd.compute_nearest_neighbor_distance()
avg_dist = np.mean(distances)
radius = 3 * avg_dist

bpa_mesh = o3d.geometry.TriangleMesh.create_from_point_cloud_ball_pivoting(
    pcd, o3d.utility.DoubleVector([radius, radius * 2])
)
dec_mesh = bpa_mesh.simplify_quadric_decimation(100000)

dec_mesh.remove_degenerate_triangles()
dec_mesh.remove_duplicated_triangles()
dec_mesh.remove_duplicated_vertices()
dec_mesh.remove_non_manifold_edges()

# Save meshes as .obj
bpa_mesh_obj_filename = filename + "_bpa_mesh.obj"
dec_mesh_obj_filename = filename + "_dec_mesh.obj"

o3d.io.write_triangle_mesh(os.path.join(script_path, bpa_mesh_obj_filename), bpa_mesh)
o3d.io.write_triangle_mesh(os.path.join(script_path, dec_mesh_obj_filename), dec_mesh)

print(f"Meshes saved as {bpa_mesh_obj_filename} and {dec_mesh_obj_filename}")

# Convert .obj to .vtk and add distance field
bpa_mesh_pv = pv.read(os.path.join(script_path, bpa_mesh_obj_filename))
dec_mesh_pv = pv.read(os.path.join(script_path, dec_mesh_obj_filename))

bpa_mesh_pv["DistanceFromOrigin"] = np.linalg.norm(bpa_mesh_pv.points, axis=1)
dec_mesh_pv["DistanceFromOrigin"] = np.linalg.norm(dec_mesh_pv.points, axis=1)

bpa_mesh_vtk_filename = filename + "_bpa_mesh.vtk"
dec_mesh_vtk_filename = filename + "_dec_mesh.vtk"

bpa_mesh_pv.save(os.path.join(script_path, bpa_mesh_vtk_filename))
dec_mesh_pv.save(os.path.join(script_path, dec_mesh_vtk_filename))
print(f"Meshes converted and saved as {bpa_mesh_vtk_filename} and {dec_mesh_vtk_filename}")



