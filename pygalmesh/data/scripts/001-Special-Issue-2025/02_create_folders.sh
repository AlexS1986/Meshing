#!/bin/bash
set -e

### 1) Set your specimen name
specimen_name="JM-25-24"

### 2) Construct working directory path
working_folder_name="${specimen_name}"  # Can be different from specimen_name if needed
working_directory="${HPC_SCRATCH}/001-Special-Issue-2025/${working_folder_name}"

### 3) Define subdirectories
seg_dir="${working_directory}/${specimen_name}_segmented/${specimen_name}_segmented_3D"
mesh_subdir="${seg_dir}/folder"

### 4) Create the directory structure
mkdir -p "${mesh_subdir}"

### 5) Copy job.sh into the working folder
if [ ! -f job.sh ]; then
  echo "❌ Error: job.sh not found in $(pwd)"
  exit 1
fi

cp job.sh "${working_directory}/job.sh"
chmod +x "${working_directory}/job.sh"
echo "Copied job.sh to ${working_directory}"

### 6) Copy config.json to working directory
if [ ! -f config.json ]; then
  echo "❌ Error: config.json not found in $(pwd)"
  exit 1
fi

cp config.json "${working_directory}/config.json"
echo "Copied config.json to ${working_directory}"

### 7) Copy metadata.json from local segmented folder to remote
local_metadata_path="${specimen_name}_segmented/metadata.json"
remote_metadata_path="${working_directory}/${specimen_name}_segmented/metadata.json"

if [ ! -f "${local_metadata_path}" ]; then
  echo "❌ Error: ${local_metadata_path} not found"
  exit 1
fi

mkdir -p "$(dirname "${remote_metadata_path}")"
cp "${local_metadata_path}" "${remote_metadata_path}"
echo "Copied metadata.json to ${remote_metadata_path}"

### 8) Copy 03_mesh_3D_array_pygalmesh.py to working directory
mesh_py_src="03_mesh_3D_array_pygalmesh.py"
if [ ! -f "${mesh_py_src}" ]; then
  echo "❌ Error: ${mesh_py_src} not found in $(pwd)"
  exit 1
fi

cp "${mesh_py_src}" "${working_directory}/"
echo "Copied ${mesh_py_src} to ${working_directory}"

### 9) Summary
echo "✅ Created working directory structure at:"
echo "   ${working_directory}"
echo "✅ Copied all necessary files successfully."












