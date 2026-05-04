import argparse
import numpy as np
from skimage import measure
import pyvista as pv
import gmsh
import meshio
import os

# =========================
# PATH SETUP (SCRIPT DIR)
# =========================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

INPUT_NPY = os.path.join(SCRIPT_DIR, "volume.npy")
SMALL_SUBDOMAIN = (40, 40, 10)


def parse_args():
    parser = argparse.ArgumentParser(description="Mesh volume data with optional debug subdomain.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--small", action="store_true", help="Process a small central subdomain for debugging.")
    group.add_argument("--full", action="store_true", help="Process the full volume. This is the default behavior.")
    parser.add_argument(
        "--subdomain",
        nargs=6,
        type=int,
        metavar=("X0", "X1", "Y0", "Y1", "Z0", "Z1"),
        help="Custom subdomain indices: x0 x1 y0 y1 z0 z1.",
    )
    parser.add_argument(
        "--output-suffix",
        default="",
        help="Append a suffix to output filenames for separate debug outputs.",
    )
    return parser.parse_args()


args = parse_args()

SUBDOMAIN = None
output_suffix = args.output_suffix

if args.subdomain is not None:
    x0, x1, y0, y1, z0, z1 = args.subdomain
    SUBDOMAIN = (slice(x0, x1), slice(y0, y1), slice(z0, z1))
    if not output_suffix:
        output_suffix = "_subdomain"
    print(f"Using custom subdomain: x={x0}:{x1}, y={y0}:{y1}, z={z0}:{z1}")
elif args.small:
    print("Using downsampled full volume for debugging.")
    vol_full = np.load(INPUT_NPY)
    # Downsample by factor of 32 in each dimension
    downsample_factor = 16
    vol = vol_full[::downsample_factor, ::downsample_factor, ::downsample_factor]
    if not output_suffix:
        output_suffix = "_small"
    print(f"Downsampled shape: {vol.shape} (from {vol_full.shape})")
else:
    print("Using full volume.")

STL_FILE = os.path.join(SCRIPT_DIR, f"geometry{output_suffix}.stl")
MSH_FILE = os.path.join(SCRIPT_DIR, f"mesh{output_suffix}.msh")
XDMF_FILE = os.path.join(SCRIPT_DIR, f"mesh{output_suffix}.xdmf")
VTK_QUALITY_FILE = os.path.join(SCRIPT_DIR, f"mesh_quality{output_suffix}.vtk")
QUALITY_TXT_FILE = os.path.join(SCRIPT_DIR, f"mesh_quality{output_suffix}.txt")


# =========================
# USER PARAMETERS
# =========================
SMOOTH_ITER = 30
DECIMATE_TARGET = 0.3   # 30% reduction

MESH_SIZE_MIN = 1.0
MESH_SIZE_MAX = 3.0

GMESH_ALGO_3D = 4  # 1=Delaunay, 4=Frontal (often better)


# =========================
# STEP 1: LOAD VOXEL DATA
# =========================
print("Loading voxel data...")
vol = np.load(INPUT_NPY)

if SUBDOMAIN is not None:
    vol = vol[SUBDOMAIN]
    print(f"Subdomain shape: {vol.shape}")


# =========================
# STEP 2: MARCHING CUBES
# =========================
print("Extracting surface (marching cubes)...")
verts, faces, normals, values = measure.marching_cubes(vol, level=0.5)

faces_pv = np.hstack([[3, f[0], f[1], f[2]] for f in faces])
surf = pv.PolyData(verts, faces_pv)
surf = surf.clean()
print(f"Initial surface: {surf.n_points} points, {surf.n_faces} faces")

# Early decimate a very large raw mesh before smoothing - SKIPPED
# if surf.n_faces > 500000:
#     reduction = min(0.95, max(0.5, 1.0 - 500000.0 / surf.n_faces))
#     print(f"Reducing initial mesh by {reduction:.1%} to improve performance...")
#     surf = surf.decimate_pro(reduction)
#     print(f"Reduced surface: {surf.n_points} points, {surf.n_faces} faces")


# =========================
# STEP 3: SMOOTHING
# =========================
print("Smoothing surface...")
iter_count = SMOOTH_ITER if surf.n_faces <= 200000 else min(10, SMOOTH_ITER)
surf_smooth = surf.smooth_taubin(n_iter=iter_count)


# =========================
# STEP 4: DECIMATION
# =========================
print("Decimating surface...")
surf_dec = surf_smooth.decimate_pro(DECIMATE_TARGET)


# =========================
# STEP 5: EXPORT STL
# =========================
print("Saving STL...")
surf_dec.save(STL_FILE)


# =========================
# STEP 6: GMESH REMESHING
# =========================
print("Running Gmsh...")

gmsh.initialize()
gmsh.model.add("mesh")

gmsh.merge(STL_FILE)

# Surface reconstruction
gmsh.model.mesh.classifySurfaces(
    angle=40 * np.pi / 180,
    boundary=True,
    forReparametrization=True
)

gmsh.model.mesh.createGeometry()

surfaces = gmsh.model.getEntities(2)

if len(surfaces) == 0:
    raise RuntimeError("No surfaces found in STL — check input geometry.")

surface_tags = [s[1] for s in surfaces]

sl = gmsh.model.geo.addSurfaceLoop(surface_tags)
gmsh.model.geo.addVolume([sl])
gmsh.model.geo.synchronize()


# =========================
# MESH SETTINGS
# =========================
gmsh.option.setNumber("Mesh.CharacteristicLengthMin", MESH_SIZE_MIN)
gmsh.option.setNumber("Mesh.CharacteristicLengthMax", MESH_SIZE_MAX)

gmsh.option.setNumber("Mesh.Algorithm3D", GMESH_ALGO_3D)

# Optimization
gmsh.option.setNumber("Mesh.Optimize", 1)
gmsh.option.setNumber("Mesh.OptimizeNetgen", 1)

print("Generating 3D mesh...")
gmsh.model.mesh.generate(3)

print("Optimizing mesh...")
gmsh.model.mesh.optimize("Netgen")

gmsh.write(MSH_FILE)
gmsh.finalize()


# =========================
# STEP 7: CONVERT TO XDMF
# =========================
print("Converting to XDMF...")
mesh = meshio.read(MSH_FILE)

tet_cells = []
for cell_block in mesh.cells:
    if cell_block.type == "tetra":
        tet_cells.append(cell_block)

if not tet_cells:
    raise RuntimeError("No tetrahedral cells were generated in the Gmsh mesh. Check the STL surface and mesh settings.")

meshio.write(
    XDMF_FILE,
    meshio.Mesh(points=mesh.points, cells=tet_cells)
)


# =========================
# STEP 8: QUALITY CHECK
# =========================
print("Computing mesh quality...")

mesh_pv = pv.read(XDMF_FILE)

quality = mesh_pv.compute_cell_quality(quality_measure="radius_ratio")

q_min = float(quality.min())
q_mean = float(quality.mean())
q_max = float(quality.max())

# Save mesh with quality field for ParaView
mesh_pv["quality"] = quality
mesh_pv.save(VTK_QUALITY_FILE)

# Save stats to text file
with open(QUALITY_TXT_FILE, "w") as f:
    f.write("Mesh quality (radius ratio)\n")
    f.write(f"Min:  {q_min}\n")
    f.write(f"Mean: {q_mean}\n")
    f.write(f"Max:  {q_max}\n")

print("\nMesh quality stats:")
print(f"Min:  {q_min}")
print(f"Mean: {q_mean}")
print(f"Max:  {q_max}")

print("\nOutputs written to:")
print(SCRIPT_DIR)

print("\nDONE.")