#!/bin/bash

# Path to your Python script
PYTHON_SCRIPT="./script.py"

# Folder to process
TARGET_FOLDER="/data/resources/2D_structure_Hannover/310125_var_bcpos_rho_10_120_004"

# Call the Python script with the folder as a parameter
python3 "$PYTHON_SCRIPT" "$TARGET_FOLDER" 
