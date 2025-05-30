#!/bin/bash

# Set the specimen name here
specimen_name="JM-25-24"

# Derived values
FOLDER_NAME="$specimen_name"
working_directory="$(pwd)"
CONFIG_PATH="${working_directory}/config.json"
NPY_PATH="${working_directory}/${specimen_name}_segmented/${specimen_name}_segmented_3D/segmented_3D_volume.py"
MESH_PATH="${working_directory}/${specimen_name}_segmented/${specimen_name}_segmented_3D/folder/mesh.xdmf"

# Generate job.sh from the template
sed \
  -e "s|{FOLDER_NAME}|${FOLDER_NAME}|g" \
  -e "s|{CONFIG_PATH}|${CONFIG_PATH}|g" \
  -e "s|{NPY_PATH}|${NPY_PATH}|g" \
  -e "s|{MESH_PATH}|${MESH_PATH}|g" \
  00_jobs/job_template.sh > job.sh

chmod +x job.sh

echo "Generated job.sh for specimen: $specimen_name"









