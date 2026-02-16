#!/bin/bash

# Path to your Python script
PYTHON_SCRIPT="./script.py"

# Folder to process
#TARGET_FOLDER="/data/resources/2D_structure_Hannover/newBCs/250925_TTO_mbb_festlager_var_a_E_var_min_max/mbb_festlager_var_a_E_min"
TARGET_FOLDER="/data/resources/2D_structure_Hannover/February2026/dcb_var_bcpos_E_min/export"

#TARGET_FOLDER="/data/resources/2D_structure_Hannover/newBCs/251008_mbb_a_10_rho_03"
# Call the Python script with the folder as a parameter
python3 "$PYTHON_SCRIPT" "$TARGET_FOLDER"  rows
