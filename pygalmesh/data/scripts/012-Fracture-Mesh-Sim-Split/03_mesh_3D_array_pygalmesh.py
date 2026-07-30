#!/usr/bin/env python3
import os
import json
import argparse
import numpy as np
import matplotlib.pyplot as plt
import nanomesh
from datetime import datetime
from skimage.transform import rescale
import pygalmesh
import traceback
import tempfile
import math
import meshio
from pathlib import Path
from scipy import ndimage as ndi
from skimage import measure


def load_config(config_path):
    with open(config_path, "r") as file:
        config = json.load(file)
    return config["03_mesh_3D_array"], config["metadata_output_path"]


def load_original_voxel_size(metadata_path):
    if not os.path.exists(metadata_path):
        raise FileNotFoundError(f"❌ Metadata file not found at: {metadata_path}")
    with open(metadata_path, "r") as f:
        metadata = json.load(f)
    return float(metadata["00_dicom2npy"]["SliceThickness"])


def plot_image_of_slice_in_subvol(script_path, subvol, z_coordinate_of_slice, filename):
    plane = subvol.select_plane(x=z_coordinate_of_slice)
    plane_array = np.array(plane.image).astype(np.float32)

    fig, ax = plt.subplots()
    ax.imshow(plane_array, cmap='gray')
    ax.axis('off')

    output_path = os.path.join(script_path, filename)
    fig.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f"✅ Saved image to {output_path}")


def structure_for_connectivity(connectivity):
    if connectivity == 6:
        return ndi.generate_binary_structure(3, 1)
    if connectivity == 18:
        return ndi.generate_binary_structure(3, 2)
    if connectivity == 26:
        return ndi.generate_binary_structure(3, 3)
    raise ValueError(f"Unsupported 3D connectivity: {connectivity}; expected 6, 18, or 26")


def keep_largest_component(mask, connectivity=6):
    labels, count = ndi.label(mask, structure=structure_for_connectivity(connectivity))
    if count <= 1:
        return mask, 0, count
    sizes = np.bincount(labels.ravel())[1:]
    keep_label = int(np.argmax(sizes) + 1)
    cleaned = labels == keep_label
    return cleaned, int(mask.sum() - cleaned.sum()), count


def build_signed_distance(mask):
    outside_distance = ndi.distance_transform_edt(~mask)
    inside_distance = ndi.distance_transform_edt(mask)
    return inside_distance - outside_distance


def extract_sdf_surface(mask, voxel_dim, params):
    pad_width = int(params.get("pad_width", 1))
    sdf_sigma_voxels = float(params.get("sdf_sigma_voxels", 0.75))
    level = float(params.get("level", 0.0))
    step_size = int(params.get("marching_cubes_step_size", 1))

    if pad_width > 0:
        mask = np.pad(mask, pad_width, mode="constant", constant_values=False)
    sdf = build_signed_distance(mask)
    if sdf_sigma_voxels > 0.0:
        sdf = ndi.gaussian_filter(sdf, sigma=sdf_sigma_voxels)

    verts, faces, normals, values = measure.marching_cubes(
        sdf.astype(np.float32, copy=False),
        level=level,
        spacing=(voxel_dim, voxel_dim, voxel_dim),
        method="lewiner",
        step_size=step_size,
        allow_degenerate=False,
    )
    if pad_width > 0:
        verts -= pad_width * voxel_dim
    return verts, faces


def repair_surface(vertices, faces, params):
    import trimesh

    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=True)
    if params.get("fill_holes", True):
        trimesh.repair.fill_holes(mesh)
    trimesh.repair.fix_winding(mesh)
    trimesh.repair.fix_normals(mesh)
    mesh.merge_vertices()

    component_filter_info = filter_surface_components(mesh, params)
    mesh = component_filter_info.pop("mesh")

    decimation_reduction = float(params.get("surface_decimation_reduction", 0.0) or 0.0)
    decimation_info = {
        "surface_decimation_reduction": decimation_reduction,
        "surface_faces_before_decimation": int(len(mesh.faces)),
    }
    if decimation_reduction > 0.0:
        import pyvista as pv

        pv_faces = np.column_stack(
            (np.full(len(mesh.faces), 3, dtype=np.int64), np.asarray(mesh.faces, dtype=np.int64))
        ).ravel()
        pv_mesh = pv.PolyData(np.asarray(mesh.vertices), pv_faces).triangulate()
        pv_decimated = pv_mesh.decimate_pro(
            decimation_reduction,
            preserve_topology=bool(params.get("surface_decimation_preserve_topology", True)),
            splitting=bool(params.get("surface_decimation_splitting", False)),
            boundary_vertex_deletion=bool(params.get("surface_decimation_boundary_vertex_deletion", False)),
        ).triangulate()
        dec_faces = pv_decimated.faces.reshape((-1, 4))[:, 1:]
        mesh = trimesh.Trimesh(vertices=np.asarray(pv_decimated.points), faces=dec_faces, process=True)
        if params.get("fill_holes", True):
            trimesh.repair.fill_holes(mesh)
        trimesh.repair.fix_winding(mesh)
        trimesh.repair.fix_normals(mesh)
        mesh.merge_vertices()

    decimation_info["surface_faces_after_decimation"] = int(len(mesh.faces))
    return np.asarray(mesh.vertices), np.asarray(mesh.faces), {
        "surface_vertices": int(len(mesh.vertices)),
        "surface_faces": int(len(mesh.faces)),
        "surface_watertight": bool(mesh.is_watertight),
        "surface_winding_consistent": bool(mesh.is_winding_consistent),
        "surface_euler_number": int(mesh.euler_number),
        "surface_components": int(len(mesh.split(only_watertight=False))),
        **component_filter_info,
        **decimation_info,
    }


def filter_surface_components(mesh, params):
    import trimesh

    min_faces = int(params.get("min_surface_component_faces", 0) or 0)
    min_area = float(params.get("min_surface_component_area", 0.0) or 0.0)
    min_volume = float(params.get("min_surface_component_abs_volume", 0.0) or 0.0)
    components = list(mesh.split(only_watertight=False))
    info = {
        "surface_components_before_filter": int(len(components)),
        "surface_component_min_faces": min_faces,
        "surface_component_min_area": min_area,
        "surface_component_min_abs_volume": min_volume,
        "surface_components_removed_by_filter": 0,
        "surface_component_faces_removed_by_filter": 0,
        "surface_component_area_removed_by_filter": 0.0,
        "surface_component_abs_volume_removed_by_filter": 0.0,
    }

    if not components or (min_faces <= 0 and min_area <= 0.0 and min_volume <= 0.0):
        info["mesh"] = mesh
        return info

    kept = []
    removed_faces = 0
    removed_area = 0.0
    removed_volume = 0.0
    for component in components:
        face_count = len(component.faces)
        area = float(component.area)
        abs_volume = abs(float(component.volume)) if component.is_watertight else 0.0
        remove = (
            (min_faces > 0 and face_count < min_faces)
            or (min_area > 0.0 and area < min_area)
            or (min_volume > 0.0 and abs_volume < min_volume)
        )
        if remove:
            removed_faces += int(face_count)
            removed_area += area
            removed_volume += abs_volume
        else:
            kept.append(component)

    if not kept:
        raise RuntimeError("Surface component filter removed all components")

    if len(kept) == len(components):
        filtered = mesh
    else:
        filtered = trimesh.util.concatenate(kept)
        filtered.merge_vertices()
        trimesh.repair.fix_winding(filtered)
        trimesh.repair.fix_normals(filtered)

    info.update({
        "mesh": filtered,
        "surface_components_removed_by_filter": int(len(components) - len(kept)),
        "surface_component_faces_removed_by_filter": int(removed_faces),
        "surface_component_area_removed_by_filter": removed_area,
        "surface_component_abs_volume_removed_by_filter": removed_volume,
    })
    return info


def surface_edge_topology(faces):
    faces = np.asarray(faces, dtype=np.int64)
    if len(faces) == 0:
        return {
            "surface_edges": 0,
            "surface_open_edges": 0,
            "surface_nonmanifold_edges": 0,
            "surface_duplicate_faces": 0,
        }

    sorted_faces = np.sort(faces, axis=1)
    _, face_counts = np.unique(sorted_faces, axis=0, return_counts=True)
    edges = np.vstack((faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]))
    edges = np.sort(edges, axis=1)
    _, edge_counts = np.unique(edges, axis=0, return_counts=True)
    return {
        "surface_edges": int(len(edge_counts)),
        "surface_open_edges": int(np.count_nonzero(edge_counts == 1)),
        "surface_nonmanifold_edges": int(np.count_nonzero(edge_counts > 2)),
        "surface_duplicate_faces": int(np.sum(face_counts - 1)),
    }


def write_surface_audit(path, info):
    lines = [
        f"Surface topology verdict: {surface_verdict(info)}",
        "",
        "Surface topology:",
    ]
    for key in [
        "surface_vertices",
        "surface_faces",
        "surface_edges",
        "surface_open_edges",
        "surface_nonmanifold_edges",
        "surface_duplicate_faces",
        "surface_watertight",
        "surface_winding_consistent",
        "surface_euler_number",
        "surface_components",
        "surface_components_before_filter",
        "surface_component_min_faces",
        "surface_component_min_area",
        "surface_component_min_abs_volume",
        "surface_components_removed_by_filter",
        "surface_component_faces_removed_by_filter",
        "surface_component_area_removed_by_filter",
        "surface_component_abs_volume_removed_by_filter",
        "surface_decimation_reduction",
        "surface_faces_before_decimation",
        "surface_faces_after_decimation",
    ]:
        if key in info:
            lines.append(f"  {key}: {info[key]}")
    lines.append("")
    Path(path).write_text("\n".join(lines))


def surface_verdict(info):
    if not info.get("surface_watertight", False):
        return "bad"
    if info.get("surface_nonmanifold_edges", 0) > 0 or info.get("surface_open_edges", 0) > 0:
        return "bad"
    if not info.get("surface_winding_consistent", False):
        return "acceptable"
    return "good"


def write_off_surface(path, vertices, faces):
    vertices = np.asarray(vertices, dtype=float)
    faces = np.asarray(faces, dtype=np.int64)
    with open(path, "w") as handle:
        handle.write("OFF\n")
        handle.write(f"{len(vertices)} {len(faces)} 0\n")
        for point in vertices:
            handle.write(f"{point[0]:.17g} {point[1]:.17g} {point[2]:.17g}\n")
        for face in faces:
            handle.write(f"3 {int(face[0])} {int(face[1])} {int(face[2])}\n")


def pygalmesh_kwargs_from_params(params, voxel_dim):
    max_element_size_factor = params.get("max_element_size_factor", 1.0)
    max_facet_distance_factor = params.get("max_facet_distance_factor", 0.1)
    max_edge_size_at_feature_edges_factor = params.get("max_edge_size_at_feature_edges_factor", 0.0)
    max_radius_surface_delaunay_ball_factor = params.get("max_radius_surface_delaunay_ball_factor", 0.0)
    return {
        "lloyd": bool(params.get("lloyd", False)),
        "odt": bool(params.get("odt", False)),
        "perturb": bool(params.get("perturb", True)),
        "exude": bool(params.get("exude", True)),
        "max_edge_size_at_feature_edges": max_edge_size_at_feature_edges_factor * voxel_dim,
        "min_facet_angle": params.get("min_facet_angle", 0.0),
        "max_radius_surface_delaunay_ball": max_radius_surface_delaunay_ball_factor * voxel_dim,
        "max_cell_circumradius": max_element_size_factor * voxel_dim,
        "max_facet_distance": max_facet_distance_factor * voxel_dim,
        "max_circumradius_edge_ratio": params.get("max_circumradius_edge_ratio", 0.0),
        "verbose": bool(params.get("verbose", True)),
        "seed": int(params.get("seed", 0)),
        "exude_time_limit": params.get("exude_time_limit", 0.0),
        "exude_sliver_bound": params.get("exude_sliver_bound", 0.0),
    }


def pygalmesh_metadata_from_params(params, voxel_dim):
    kwargs = pygalmesh_kwargs_from_params(params, voxel_dim)
    return {
        "max_element_size_factor": params.get("max_element_size_factor", 1.0),
        "max_facet_distance_factor": params.get("max_facet_distance_factor", 0.1),
        "max_edge_size_at_feature_edges_factor": params.get("max_edge_size_at_feature_edges_factor", 0.0),
        "max_radius_surface_delaunay_ball_factor": params.get("max_radius_surface_delaunay_ball_factor", 0.0),
        **kwargs,
    }


def write_sdf_pygalmesh_mesh(vertices, faces, mesh_output_path, voxel_dim, params):
    mesh_output_path = os.path.abspath(mesh_output_path)
    output_dir = os.path.dirname(mesh_output_path)
    os.makedirs(output_dir, exist_ok=True)

    surface_path = os.path.splitext(mesh_output_path)[0] + "_sdf_surface.off"
    write_off_surface(surface_path, vertices, faces)

    pygalmesh_params = dict(params.get("pygalmesh_parameters", {}))
    generate_kwargs = pygalmesh_kwargs_from_params(pygalmesh_params, voxel_dim)
    reorient = bool(params.get("reorient", False))
    mesh = pygalmesh.generate_volume_mesh_from_surface_mesh(
        surface_path,
        **generate_kwargs,
        reorient=reorient,
    )
    mesh.write(mesh_output_path)
    return {
        "surface_off_path": surface_path,
        "reorient": reorient,
        "pygalmesh_parameters": pygalmesh_metadata_from_params(pygalmesh_params, voxel_dim),
    }


def write_sdf_gmsh_mesh(vertices, faces, mesh_output_path, voxel_dim, params):
    import gmsh

    mesh_output_path = os.path.abspath(mesh_output_path)
    output_dir = os.path.dirname(mesh_output_path)
    os.makedirs(output_dir, exist_ok=True)
    stl_path = os.path.splitext(mesh_output_path)[0] + "_sdf_surface.stl"
    msh_path = os.path.splitext(mesh_output_path)[0] + "_sdf_gmsh.msh"

    surface_mesh = meshio.Mesh(vertices, [("triangle", faces.astype(np.int64, copy=False))])
    meshio.write(stl_path, surface_mesh, file_format="stl")

    mesh_size_min = float(params.get("mesh_size_min_factor", 0.5)) * voxel_dim
    mesh_size_max = float(params.get("mesh_size_max_factor", 5.0)) * voxel_dim
    classification_angle = math.radians(float(params.get("classification_angle_degrees", 40.0)))
    curve_angle = math.radians(float(params.get("curve_angle_degrees", 180.0)))
    force_parametrizable = bool(params.get("force_parametrizable_patches", True))
    include_boundary = bool(params.get("include_boundary", True))
    optimize_methods = params.get("optimize_methods", ["Netgen"])
    verbose = bool(params.get("verbose", True))

    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 1 if verbose else 0)
        gmsh.option.setNumber("Mesh.MeshSizeMin", mesh_size_min)
        gmsh.option.setNumber("Mesh.MeshSizeMax", mesh_size_max)
        gmsh.option.setNumber("Mesh.Algorithm3D", int(params.get("algorithm3d", 10)))
        gmsh.model.add("sdf_surface")
        gmsh.merge(stl_path)
        gmsh.model.mesh.classifySurfaces(
            classification_angle,
            include_boundary,
            force_parametrizable,
            curve_angle,
        )
        gmsh.model.mesh.createGeometry()
        surfaces = [tag for dim, tag in gmsh.model.getEntities(2)]
        if not surfaces:
            raise RuntimeError("Gmsh did not create any surfaces from the signed-distance STL")
        surface_loop = gmsh.model.geo.addSurfaceLoop(surfaces)
        volume = gmsh.model.geo.addVolume([surface_loop])
        gmsh.model.geo.synchronize()
        gmsh.model.addPhysicalGroup(2, surfaces, 1)
        gmsh.model.addPhysicalGroup(3, [volume], 1)
        gmsh.model.mesh.generate(3)
        for method in optimize_methods:
            gmsh.model.mesh.optimize(str(method))
        gmsh.write(msh_path)
    finally:
        gmsh.finalize()

    gmsh_mesh = meshio.read(msh_path)
    tetra_blocks = [block.data for block in gmsh_mesh.cells if block.type == "tetra"]
    if not tetra_blocks:
        raise RuntimeError(f"No tetrahedral cells found in Gmsh output: {msh_path}")
    tetra_cells = np.vstack(tetra_blocks)
    out_mesh = meshio.Mesh(
        gmsh_mesh.points[:, :3],
        [("tetra", tetra_cells)],
        cell_data={"medit:ref": [np.ones(len(tetra_cells), dtype=np.int32)]},
    )
    meshio.write(mesh_output_path, out_mesh)
    return {
        "surface_stl_path": stl_path,
        "gmsh_msh_path": msh_path,
        "gmsh_mesh_size_min": mesh_size_min,
        "gmsh_mesh_size_max": mesh_size_max,
        "gmsh_tetrahedra": int(len(tetra_cells)),
        "gmsh_points": int(len(gmsh_mesh.points)),
    }


def main():
    script_path = os.path.dirname(__file__)
    default_config_path = os.path.join(script_path, "config.json")

    parser = argparse.ArgumentParser(description="Generate a 3D mesh from segmented volume slices.")
    parser.add_argument("--config", type=str, default=default_config_path, help="Path to configuration JSON file")
    parser.add_argument("--npy", type=str, default=os.path.join(script_path,"volume.npy"), help="Path to the input .npy volume file (overrides config)")
    parser.add_argument("--mesh", type=str, default=os.path.join(script_path,"mesh.xdmf"), help="Path to save the output mesh file (overrides config)")
    args = parser.parse_args()

    config_path = args.config
    config, metadata_output_path = load_config(config_path)

    specimen_name = config["specimen_name"]
    x_range = tuple(config.get("x_range", [0, 0]))  # updated after load if needed
    smoothing_sigma = config["smoothing_sigma_factor"]
    segmentation_algorithm = config["segmentation_algorithm"]
    z_slice = config["z_slice"]
    scale_factor = config["scale_factor"]
    meshing_method = config.get("meshing_method", "pygalmesh").lower()

    # Use provided npy file or fallback to config
    if args.npy:
        input_path = args.npy
    else:
        input_folder = config["input_folder"]
        input_path = os.path.join(input_folder, "segmented_3D_volume.npy")

    # Use provided mesh path or fallback to config
    mesh_output_path = args.mesh if args.mesh else os.path.join(config["mesh_output_path"])

    original_voxel_size = load_original_voxel_size(metadata_output_path)

    print(f"📦 Loading volume from: {input_path}")
    intensity_at_voxels = np.load(input_path)
    vol = nanomesh.Image(intensity_at_voxels)

    if x_range == (0, 0):
        x_range = (0, vol.image.shape[0])

    plot_image_of_slice_in_subvol(script_path, vol, 0, "vol_output_plane.png")

    # Process and segment
    subvol = vol.select_subvolume(xs=x_range)
    plot_image_of_slice_in_subvol(script_path, subvol, z_slice, "subvol_output_plane.png")

    subvol_gauss = subvol.apply(rescale, scale=scale_factor).gaussian(sigma=smoothing_sigma * original_voxel_size)
    subvol_seg = subvol_gauss.binary_digitize(threshold=segmentation_algorithm).invert_contrast()
    plot_image_of_slice_in_subvol(script_path, subvol_seg, z_slice, "subvol_seg_output_plane.png")

    voxel_dim = original_voxel_size / scale_factor
    voxel_size = (voxel_dim, voxel_dim, voxel_dim)

    mesh_metadata = {
        "specimen_name": specimen_name,
        "input_volume_shape": vol.image.shape,
        "subvolume_bounds": {"x_range": list(x_range)},
        "smoothing_sigma": smoothing_sigma,
        "threshold_method": segmentation_algorithm,
        "scale_factor": scale_factor,
        "voxel_size": voxel_size,
        "voxel_dim": voxel_dim,
        "mesh_output_path": mesh_output_path,
        "meshing_method": meshing_method,
        "timestamp": datetime.now().isoformat()
    }

    os.makedirs(os.path.dirname(mesh_output_path), exist_ok=True)

    if meshing_method == "pygalmesh":
        params = config.get("pygalmesh_parameters", {})
        max_element_size_factor = params.get("max_element_size_factor", 1.0)
        max_facet_distance_factor = params.get("max_facet_distance_factor", 0.1)
        exude_time_limit = params.get("exude_time_limit", 0.0)
        exude_sliver_bound = params.get("exude_sliver_bound", 0.0)
        lloyd = bool(params.get("lloyd", False))
        odt = bool(params.get("odt", False))
        perturb = bool(params.get("perturb", True))
        exude = bool(params.get("exude", True))
        max_edge_size_at_feature_edges_factor = params.get("max_edge_size_at_feature_edges_factor", 0.0)
        min_facet_angle = params.get("min_facet_angle", 0.0)
        max_radius_surface_delaunay_ball_factor = params.get("max_radius_surface_delaunay_ball_factor", 0.0)
        max_circumradius_edge_ratio = params.get("max_circumradius_edge_ratio", 0.0)
        seed = int(params.get("seed", 0))
        verbose = bool(params.get("verbose", True))

        vol_pygal = np.array(subvol_seg.image, dtype=np.uint8)
        unique_values, unique_counts = np.unique(vol_pygal, return_counts=True)
        mesh_metadata["segmented_volume_value_counts"] = {
            str(int(value)): int(count)
            for value, count in zip(unique_values, unique_counts)
        }
        print(f"📊 Segmented volume shape: {vol_pygal.shape}")
        print(f"📊 Segmented value counts: {mesh_metadata['segmented_volume_value_counts']}")
        print(
            "📐 Pygalmesh parameters: "
            f"max_cell_circumradius={max_element_size_factor * voxel_dim}, "
            f"max_facet_distance={max_facet_distance_factor * voxel_dim}, "
            f"max_edge_size_at_feature_edges={max_edge_size_at_feature_edges_factor * voxel_dim}, "
            f"min_facet_angle={min_facet_angle}, "
            f"max_radius_surface_delaunay_ball={max_radius_surface_delaunay_ball_factor * voxel_dim}, "
            f"max_circumradius_edge_ratio={max_circumradius_edge_ratio}, "
            f"lloyd={lloyd}, odt={odt}, perturb={perturb}, exude={exude}, "
            f"exude_time_limit={exude_time_limit}, "
            f"exude_sliver_bound={exude_sliver_bound}, seed={seed}"
        )

        try:
            generate_kwargs = {
                "lloyd": lloyd,
                "odt": odt,
                "perturb": perturb,
                "exude": exude,
                "max_edge_size_at_feature_edges": max_edge_size_at_feature_edges_factor * voxel_dim,
                "min_facet_angle": min_facet_angle,
                "max_radius_surface_delaunay_ball": max_radius_surface_delaunay_ball_factor * voxel_dim,
                "max_cell_circumradius": max_element_size_factor * voxel_dim,
                "max_facet_distance": max_facet_distance_factor * voxel_dim,
                "max_circumradius_edge_ratio": max_circumradius_edge_ratio,
                "verbose": verbose,
                "seed": seed,
            }
            if exude_time_limit or exude_sliver_bound:
                with tempfile.NamedTemporaryFile(suffix=".inr", delete=False) as handle:
                    inr_path = handle.name
                try:
                    pygalmesh.save_inr(vol_pygal, voxel_size, inr_path)
                    mesh = pygalmesh.generate_from_inr(
                        inr_path,
                        **generate_kwargs,
                        exude_time_limit=exude_time_limit,
                        exude_sliver_bound=exude_sliver_bound
                    )
                finally:
                    if os.path.exists(inr_path):
                        os.remove(inr_path)
            else:
                mesh = pygalmesh.generate_from_array(vol_pygal, voxel_size, **generate_kwargs)
        except ValueError as exc:
            print("❌ pygalmesh failed while reading the generated temporary mesh.")
            print("   This often means the generated mesh file was truncated, commonly")
            print("   because the mesh became too large for the available scratch space,")
            print("   memory, or wall time. Try a larger reduce factor, coarser")
            print("   pygalmesh parameters, or smaller/partitioned subvolumes.")
            print("   Original exception:")
            traceback.print_exc()
            raise
        mesh.write(mesh_output_path)

        mesh_metadata["pygalmesh_parameters"] = {
            "max_element_size_factor": max_element_size_factor,
            "max_facet_distance_factor": max_facet_distance_factor,
            "max_edge_size_at_feature_edges_factor": max_edge_size_at_feature_edges_factor,
            "max_radius_surface_delaunay_ball_factor": max_radius_surface_delaunay_ball_factor,
            "max_cell_circumradius": max_element_size_factor * voxel_dim,
            "max_facet_distance": max_facet_distance_factor * voxel_dim,
            "max_edge_size_at_feature_edges": max_edge_size_at_feature_edges_factor * voxel_dim,
            "min_facet_angle": min_facet_angle,
            "max_radius_surface_delaunay_ball": max_radius_surface_delaunay_ball_factor * voxel_dim,
            "max_circumradius_edge_ratio": max_circumradius_edge_ratio,
            "lloyd": lloyd,
            "odt": odt,
            "perturb": perturb,
            "exude": exude,
            "exude_time_limit": exude_time_limit,
            "exude_sliver_bound": exude_sliver_bound,
            "seed": seed,
            "verbose": verbose
        }

    elif meshing_method in ("sdf_gmsh", "signed_distance_gmsh"):
        params = config.get("sdf_gmsh_parameters", {})
        material_value = int(params.get("material_value", 1))
        keep_largest = bool(params.get("keep_largest_component", False))
        component_connectivity = int(params.get("component_connectivity", 6))

        segmented = np.array(subvol_seg.image, dtype=np.uint8)
        material_mask = segmented == material_value
        original_material_voxels = int(material_mask.sum())
        removed_component_voxels = 0
        component_count = None
        if keep_largest:
            material_mask, removed_component_voxels, component_count = keep_largest_component(
                material_mask,
                connectivity=component_connectivity,
            )

        unique_values, unique_counts = np.unique(material_mask.astype(np.uint8), return_counts=True)
        mesh_metadata["segmented_volume_value_counts"] = {
            str(int(value)): int(count)
            for value, count in zip(unique_values, unique_counts)
        }
        print(f"📊 Signed-distance source volume shape: {material_mask.shape}")
        print(f"📊 Signed-distance material voxels: {int(material_mask.sum())} / {material_mask.size}")
        print(
            "📐 SDF/Gmsh parameters: "
            f"sdf_sigma_voxels={params.get('sdf_sigma_voxels', 0.75)}, "
            f"pad_width={params.get('pad_width', 1)}, "
            f"mesh_size_min_factor={params.get('mesh_size_min_factor', 0.5)}, "
            f"mesh_size_max_factor={params.get('mesh_size_max_factor', 5.0)}, "
            f"keep_largest_component={keep_largest}"
        )

        vertices, faces = extract_sdf_surface(material_mask, voxel_dim, params)
        vertices, faces, surface_info = repair_surface(vertices, faces, params)
        gmsh_info = write_sdf_gmsh_mesh(vertices, faces, mesh_output_path, voxel_dim, params)

        mesh_metadata["sdf_gmsh_parameters"] = dict(params)
        mesh_metadata["sdf_gmsh_surface"] = surface_info
        mesh_metadata["sdf_gmsh_output"] = gmsh_info
        mesh_metadata["sdf_gmsh_voxel_cleanup"] = {
            "original_material_voxels": original_material_voxels,
            "used_material_voxels": int(material_mask.sum()),
            "removed_component_voxels": removed_component_voxels,
            "component_count_before_keep_largest": component_count,
            "keep_largest_component": keep_largest,
            "component_connectivity": component_connectivity,
        }

    elif meshing_method in ("sdf_pygalmesh", "signed_distance_pygalmesh"):
        params = config.get("sdf_pygalmesh_parameters", {})
        material_value = int(params.get("material_value", 1))
        keep_largest = bool(params.get("keep_largest_component", False))
        component_connectivity = int(params.get("component_connectivity", 6))
        require_watertight = bool(params.get("require_watertight_surface", True))

        segmented = np.array(subvol_seg.image, dtype=np.uint8)
        material_mask = segmented == material_value
        original_material_voxels = int(material_mask.sum())
        removed_component_voxels = 0
        component_count = None
        if keep_largest:
            material_mask, removed_component_voxels, component_count = keep_largest_component(
                material_mask,
                connectivity=component_connectivity,
            )

        unique_values, unique_counts = np.unique(material_mask.astype(np.uint8), return_counts=True)
        mesh_metadata["segmented_volume_value_counts"] = {
            str(int(value)): int(count)
            for value, count in zip(unique_values, unique_counts)
        }
        print(f"📊 SDF/pygalmesh source volume shape: {material_mask.shape}")
        print(f"📊 SDF/pygalmesh material voxels: {int(material_mask.sum())} / {material_mask.size}")
        print(
            "📐 SDF/pygalmesh parameters: "
            f"sdf_sigma_voxels={params.get('sdf_sigma_voxels', 0.75)}, "
            f"pad_width={params.get('pad_width', 1)}, "
            f"keep_largest_component={keep_largest}, "
            f"require_watertight_surface={require_watertight}"
        )

        vertices, faces = extract_sdf_surface(material_mask, voxel_dim, params)
        vertices, faces, surface_info = repair_surface(vertices, faces, params)
        surface_info.update(surface_edge_topology(faces))
        surface_report_path = os.path.splitext(mesh_output_path)[0] + "_sdf_surface.topology.txt"
        write_surface_audit(surface_report_path, surface_info)
        print(f"Wrote SDF surface topology audit: {surface_report_path}")
        print(f"SDF surface topology verdict: {surface_verdict(surface_info)}")

        if require_watertight and surface_verdict(surface_info) == "bad":
            raise RuntimeError(
                "SDF surface is not watertight/manifold enough for volume meshing; "
                f"see {surface_report_path}"
            )

        pygalmesh_info = write_sdf_pygalmesh_mesh(vertices, faces, mesh_output_path, voxel_dim, params)

        mesh_metadata["sdf_pygalmesh_parameters"] = dict(params)
        mesh_metadata["sdf_pygalmesh_surface"] = {
            **surface_info,
            "surface_report_path": surface_report_path,
        }
        mesh_metadata["sdf_pygalmesh_output"] = pygalmesh_info
        mesh_metadata["sdf_pygalmesh_voxel_cleanup"] = {
            "original_material_voxels": original_material_voxels,
            "used_material_voxels": int(material_mask.sum()),
            "removed_component_voxels": removed_component_voxels,
            "component_count_before_keep_largest": component_count,
            "keep_largest_component": keep_largest,
            "component_connectivity": component_connectivity,
        }

    elif meshing_method == "nanomesh":
        params = config.get("nanomesh_parameters", {})
        meshing_options = params.get("meshing_options", "-pq")
        output_format = params.get("output_format", "gmsh22")
        output_binary = params.get("output_binary", False)

        mesher = nanomesh.Mesher(subvol_seg)
        mesher.generate_contour()
        mesh = mesher.tetrahedralize(opts=meshing_options)
        mesh.write(mesh_output_path, file_format=output_format, binary=output_binary)

        mesh_metadata["nanomesh_parameters"] = {
            "meshing_options": meshing_options,
            "output_format": output_format,
            "output_binary": output_binary
        }

    else:
        raise ValueError(f"Unsupported meshing method: {meshing_method}")

    # Update metadata
    if not os.path.exists(metadata_output_path):
        raise FileNotFoundError(f"❌ Metadata file not found at: {metadata_output_path}")

    with open(metadata_output_path, "r") as f:
        existing_metadata = json.load(f)

    existing_metadata["03_mesh_3D_array"] = mesh_metadata

    with open(metadata_output_path, "w") as f:
        json.dump(existing_metadata, f, indent=4)

    print(f"✅ Mesh and metadata appended to {metadata_output_path}")


if __name__ == "__main__":
    main()
