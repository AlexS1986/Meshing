#!/usr/bin/env python3
"""Turn the binary voxel volume into a tetrahedral mesh (SDF -> CGAL).

Differences to 010-Yield-Surface-Generation/03_mesh_3D_array_pygalmesh.py
------------------------------------------------------------------------
1. Only the ``sdf_pygalmesh`` path remains. The unused ``pygalmesh`` (INR),
   ``nanomesh`` and ``sdf_gmsh`` backends and their config blocks are gone,
   together with the nanomesh dependency.
2. The phantom re-segmentation is gone. 010 fed the already binary array
   through ``gaussian(...) -> binary_digitize('otsu') -> invert_contrast()``
   before building the mask. On a {0,1} array the Gaussian was a no-op (sigma
   in mm, see 01) and ``digitize + invert`` is exactly a complement, so the
   whole chain reduced to ``material_mask = (volume == 0)``. That is what is
   done here explicitly, and it is asserted at runtime.

   *** The mask handed to marching_cubes and pygalmesh is bit-identical to
   010. Nothing about the 0/1 meaning changed. ***

   Array value 0 = aluminium = the meshed phase (``meshed_phase_array_value``).
   Array value 1 = pore / air. See 01_segment_slice_wise.py and
   02d_axis_aligned_cuboid_crop.py, whose shell value 0 relies on this.
3. Dead parameters removed: ``scale_factor``, ``smoothing_sigma_factor``,
   ``segmentation_algorithm``, ``z_slice``, ``x_range``, ``specimen_name``.
   The voxel edge length is taken from the metadata as before.
"""

import argparse
import json
import os
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import ndimage as ndi
from skimage import measure

# pygalmesh is only needed for the actual CGAL call and is not available
# outside the meshing container. Imported lazily in write_sdf_pygalmesh_mesh
# so that the voxel-side helpers stay importable (verify_pipeline.py).


def load_original_voxel_size(metadata_path):
    """Isotropic voxel edge length in mm.

    Only SliceThickness is stored/used; 00_dicom_2_npy.py asserts that it
    agrees with PixelSpacing, so the isotropy assumption is checked and not
    merely hoped for.
    """
    if not os.path.exists(metadata_path):
        raise FileNotFoundError(f"Metadata file not found at: {metadata_path}")
    with open(metadata_path, "r") as handle:
        metadata = json.load(handle)
    return float(metadata["00_dicom2npy"]["SliceThickness"])


def save_slice_preview(volume, index, output_path):
    fig, ax = plt.subplots()
    ax.imshow(np.asarray(volume[index], dtype=np.float32), cmap="gray", interpolation="nearest")
    ax.axis("off")
    fig.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def build_material_mask(volume, meshed_phase_array_value):
    """Voxels that become solid material in the FE mesh.

    Equivalent to 010's ``binary_digitize('otsu').invert_contrast()`` followed
    by ``== 1`` for a binary input array, but without the detour.
    """
    unique = np.unique(volume)
    if not np.all(np.isin(unique, (0, 1))):
        raise ValueError(
            f"Expected a binary {{0,1}} voxel array, found values {unique[:10]}. "
            "03 must run on the output of 01/02*, not on grey values."
        )
    return volume == meshed_phase_array_value
def load_config(config_path):
    with open(config_path, "r") as file:
        config = json.load(file)
    return config["03_mesh_3D_array"], config["metadata_output_path"]


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
    import pygalmesh

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


def main():
    script_path = os.path.dirname(os.path.abspath(__file__))
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", default=os.path.join(script_path, "config.json"))
    parser.add_argument("--npy", default=os.path.join(script_path, "volume.npy"),
                        help="Binary voxel volume to mesh")
    parser.add_argument("--mesh", default=os.path.join(script_path, "mesh.xdmf"),
                        help="Output mesh path")
    args = parser.parse_args()

    config, metadata_output_path = load_config(args.config)
    params = config.get("sdf_pygalmesh_parameters", {})

    mesh_output_path = os.path.abspath(args.mesh)
    os.makedirs(os.path.dirname(mesh_output_path), exist_ok=True)

    voxel_dim = load_original_voxel_size(metadata_output_path)

    print(f"Loading volume: {args.npy}")
    volume = np.load(args.npy)
    print(f"Volume shape: {volume.shape}, voxel edge: {voxel_dim:g} mm (isotropic)")

    meshed_phase_array_value = int(params.get("meshed_phase_array_value", 0))
    material_mask = build_material_mask(volume, meshed_phase_array_value)
    original_material_voxels = int(material_mask.sum())

    keep_largest = bool(params.get("keep_largest_component", False))
    component_connectivity = int(params.get("component_connectivity", 6))
    removed_component_voxels = 0
    component_count = None
    if keep_largest:
        material_mask, removed_component_voxels, component_count = keep_largest_component(
            material_mask, connectivity=component_connectivity
        )

    solid_fraction = original_material_voxels / material_mask.size
    print(f"Meshed phase = array value {meshed_phase_array_value} (aluminium)")
    print(f"Solid voxels: {original_material_voxels} / {material_mask.size} "
          f"(solid volume fraction {solid_fraction:.4f}, porosity {1.0 - solid_fraction:.4f})")
    print(f"SDF parameters: sdf_sigma_voxels={params.get('sdf_sigma_voxels', 1.0)}, "
          f"pad_width={params.get('pad_width', 1)}, "
          f"keep_largest_component={keep_largest}")

    save_slice_preview(material_mask.astype(np.uint8), material_mask.shape[0] // 2,
                       os.path.splitext(mesh_output_path)[0] + "_meshed_phase_preview.png")

    mesh_metadata = {
        "input_volume": os.path.abspath(args.npy),
        "input_volume_shape": list(volume.shape),
        "voxel_dim_mm": voxel_dim,
        "meshing_method": "sdf_pygalmesh",
        "meshed_phase_array_value": meshed_phase_array_value,
        "solid_volume_fraction": solid_fraction,
        "porosity": 1.0 - solid_fraction,
        "mesh_output_path": mesh_output_path,
        "timestamp": datetime.now().isoformat(),
    }

    vertices, faces = extract_sdf_surface(material_mask, voxel_dim, params)
    vertices, faces, surface_info = repair_surface(vertices, faces, params)
    surface_info.update(surface_edge_topology(faces))

    surface_report_path = os.path.splitext(mesh_output_path)[0] + "_sdf_surface.topology.txt"
    write_surface_audit(surface_report_path, surface_info)
    verdict = surface_verdict(surface_info)
    print(f"Surface topology audit: {surface_report_path} -> {verdict}")

    if bool(params.get("require_watertight_surface", True)) and verdict == "bad":
        raise RuntimeError(
            f"SDF surface is not watertight/manifold enough for volume meshing; see {surface_report_path}"
        )

    pygalmesh_info = write_sdf_pygalmesh_mesh(vertices, faces, mesh_output_path, voxel_dim, params)

    mesh_metadata["sdf_pygalmesh_parameters"] = dict(params)
    mesh_metadata["sdf_pygalmesh_surface"] = {**surface_info, "surface_report_path": surface_report_path}
    mesh_metadata["sdf_pygalmesh_output"] = pygalmesh_info
    mesh_metadata["voxel_component_filter"] = {
        "keep_largest_component": keep_largest,
        "component_connectivity": component_connectivity,
        "solid_voxels_before": original_material_voxels,
        "solid_voxels_used": int(material_mask.sum()),
        "removed_component_voxels": removed_component_voxels,
        "component_count_before_keep_largest": component_count,
    }

    with open(metadata_output_path, "r") as handle:
        metadata = json.load(handle)
    metadata["03_mesh_3D_array"] = mesh_metadata
    with open(metadata_output_path, "w") as handle:
        json.dump(metadata, handle, indent=4)

    print(f"Mesh written to {mesh_output_path}; metadata appended to {metadata_output_path}")


if __name__ == "__main__":
    main()
