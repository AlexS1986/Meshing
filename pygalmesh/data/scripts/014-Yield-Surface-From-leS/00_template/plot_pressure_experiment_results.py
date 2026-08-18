import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os

# Read the data from file
script_path = os.path.dirname(__file__)
file_path = os.path.join(script_path,'linearelastic_pressure_test_graphs.txt') # Adjust filename if needed
df = pd.read_csv(file_path, delim_whitespace=True, header=None)

# Assign column names
df.columns = ['time_s', 'vol_percent_exceeding_sigma_vm', 'reaction_force_x']

# Compute absolute values and derived columns
df['displacement_abs_mm'] = np.abs(-df['time_s'])  # Applied displacement in mm
df['reaction_force_abs'] = np.abs(df['reaction_force_x'])
df['vol_percent'] = df['vol_percent_exceeding_sigma_vm'] * 100  # Volume %

# Output directory (same as script location)
output_dir = os.path.dirname(os.path.abspath(__file__))

# Plot 1: Absolute Reaction Force vs Absolute Displacement (mm)
plt.figure(figsize=(8, 5))
plt.plot(df['displacement_abs_mm'], df['reaction_force_abs'], 'r-', label='|Reaction Force X|')
plt.xlabel('Absolute Displacement in X (mm)')
plt.ylabel('Absolute Reaction Force (N)')
plt.title('Reaction Force vs Displacement')
plt.grid(True)
plt.legend()
plt.tight_layout()
plt.savefig(os.path.join(output_dir, 'reaction_force_vs_displacement.png'))
plt.close()

# Plot 2: Volume Percentage vs Absolute Reaction Force
plt.figure(figsize=(8, 5))
plt.plot(df['reaction_force_abs'], df['vol_percent'], 'b--', label='Volume % > σ_vm')
plt.xlabel('Absolute Reaction Force (N)')
plt.ylabel('Volume Percentage (%)')
plt.title('Volume % vs Reaction Force')
plt.grid(True)
plt.legend()
plt.tight_layout()
plt.savefig(os.path.join(output_dir, 'volume_percent_vs_reaction_force.png'))
plt.close()

# Plot 3: Volume Percentage vs Absolute Displacement (mm)
plt.figure(figsize=(8, 5))
plt.plot(df['displacement_abs_mm'], df['vol_percent'], 'g-.', label='Volume % > σ_vm')
plt.xlabel('Absolute Displacement in X (mm)')
plt.ylabel('Volume Percentage (%)')
plt.title('Volume % vs Displacement')
plt.grid(True)
plt.legend()
plt.tight_layout()
plt.savefig(os.path.join(output_dir, 'volume_percent_vs_displacement.png'))
plt.close()
