#!/bin/bash

# Set the specimen name here
specimen_name="JM-25-24"

# Base path to scripts
#base_path_to_scripts="/data/scripts/001-Special-Issue-2025"
base_path_to_scripts="."

# Derived values
FOLDER_NAME="$specimen_name"
working_directory="$(pwd)"
CONFIG_PATH="${base_path_to_scripts}/config.json"
NPY_PATH="${base_path_to_scripts}/${specimen_name}_segmented/${specimen_name}_segmented_3D/segmented_3D_volume.py"
MESH_PATH="${base_path_to_scripts}/${specimen_name}_segmented/${specimen_name}_segmented_3D/folder/mesh.xdmf"

# Generate job.sh from the template
sed \
  -e "s|{FOLDER_NAME}|${FOLDER_NAME}|g" \
  -e "s|{CONFIG_PATH}|${CONFIG_PATH}|g" \
  -e "s|{NPY_PATH}|${NPY_PATH}|g" \
  -e "s|{MESH_PATH}|${MESH_PATH}|g" \
  00_jobs/job_template.sh > job.sh

chmod +x job.sh

echo "Generated job.sh for specimen: $specimen_name"










