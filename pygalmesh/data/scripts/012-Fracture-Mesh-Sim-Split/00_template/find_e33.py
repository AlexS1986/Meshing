import json
import os
import numpy as np

script_dir = os.path.dirname(os.path.abspath(__file__))

tolerance = 1e-1  # Threshold to detect axis-aligned directions

def extract_moduli(input_basename, output_prefix):
    input_file = os.path.join(script_dir, f"{input_basename}.plt")
    
    label11 = f"{output_prefix}11"
    label22 = f"{output_prefix}22"
    label33 = f"{output_prefix}33"
    label_max = f"{output_prefix}max"
    label_min = f"{output_prefix}min"

    values_to_save = {
        label11: None,
        label22: None,
        label33: None
    }

    data = []

    # Load and parse the data
    with open(input_file, 'r') as f:
        lines = f.readlines()

    for line in lines:
        parts = line.strip().split()
        if len(parts) == 3:
            try:
                vec = np.array([float(parts[0]), float(parts[1]), float(parts[2])])
                data.append(vec)
            except ValueError:
                continue

    data = np.array(data)
    if data.shape[0] == 0:
        print(f"[{input_basename}] No valid data points found.")
        return

    # Find directional moduli
    for vec in data:
        if values_to_save[label11] is None and abs(vec[1]) < tolerance and abs(vec[2]) < tolerance:
            values_to_save[label11] = abs(vec[0])
        if values_to_save[label22] is None and abs(vec[0]) < tolerance and abs(vec[2]) < tolerance:
            values_to_save[label22] = abs(vec[1])
        if values_to_save[label33] is None and abs(vec[0]) < tolerance and abs(vec[1]) < tolerance:
            values_to_save[label33] = abs(vec[2])
        if all(v is not None for v in values_to_save.values()):
            break

    # Compute max and min values and corresponding directions
    magnitudes = np.linalg.norm(data, axis=1)
    max_idx = np.argmax(magnitudes)
    min_idx = np.argmin(magnitudes)

    max_val = magnitudes[max_idx]
    min_val = magnitudes[min_idx]

    max_dir = data[max_idx] / np.linalg.norm(data[max_idx])
    min_dir = data[min_idx] / np.linalg.norm(data[min_idx])

    result = {
        **values_to_save,
        label_max: {
            "value": max_val,
            "direction": max_dir.tolist()
        },
        label_min: {
            "value": min_val,
            "direction": min_dir.tolist()
        }
    }

    # Save JSON
    output_file = os.path.join(script_dir, f"{output_prefix}_moduli.json")
    with open(output_file, 'w') as f:
        json.dump(result, f, indent=4)

    print(f"[{input_basename}] Moduli saved to {output_file}")

# Run for both emodul and gmodul
extract_moduli("emodul", "E")
extract_moduli("gmodul", "G")




