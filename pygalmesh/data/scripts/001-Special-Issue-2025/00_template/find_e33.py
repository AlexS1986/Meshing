import json
import os

script_dir = os.path.dirname(os.path.abspath(__file__))

input_file = 'emodul.plt'
output_file = 'E33.json'

input_file = os.path.join(script_dir, input_file)
output_file = os.path.join(script_dir, output_file)

tolerance = 1e-1  # Define how small is "very small"

with open(input_file, 'r') as f:
    lines = f.readlines()

value_to_save = None

# Skip header lines that don't contain data
for line in lines:
    line = line.strip()
    parts = line.split()
    if len(parts) == 3:
        try:
            col1 = float(parts[0])
            col2 = float(parts[1])
            col3 = float(parts[2])

            if abs(col1) < tolerance and abs(col2) < tolerance:
                value_to_save = abs(col3)
                break
        except ValueError:
            continue

if value_to_save is not None:
    with open(output_file, 'w') as f:
        json.dump({"value": value_to_save}, f, indent=4)
    print(f"Value saved to {output_file}: {value_to_save}")
else:
    print("No row with first two columns near zero found.")

