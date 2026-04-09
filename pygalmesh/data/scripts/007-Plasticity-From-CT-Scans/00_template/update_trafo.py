import json
import os

def format_fortran_number(num):
    # Format a float number into Fortran double precision style: 1.2345d+02
    # Use lowercase 'd' and scientific notation with sign
    return f"{num:.6e}".replace("e", "d")

def main():
    # Files in the same directory as script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(script_dir, "Chom.json")
    trafo_path = os.path.join(script_dir, "trafo.f")

    # Load JSON matrix
    with open(json_path, "r") as f:
        matrix = json.load(f)

    if len(matrix) != 6 or any(len(row) != 6 for row in matrix):
        raise ValueError("Matrix must be 6x6")

    # Read trafo.f content
    with open(trafo_path, "r") as f:
        trafo_content = f.read()

    # Prepare replacements dictionary for all {Cxy}
    replacements = {
        "C11": matrix[0][0],
        "C12": matrix[0][1],
        "C13": matrix[0][2],
        "C14": matrix[0][3],
        "C15": matrix[0][4],
        "C16": matrix[0][5],
        "C22": matrix[1][1],
        "C23": matrix[1][2],
        "C24": matrix[1][3],
        "C25": matrix[1][4],
        "C26": matrix[1][5],
        "C33": matrix[2][2],
        "C34": matrix[2][3],
        "C35": matrix[2][4],
        "C36": matrix[2][5],
        "C41": matrix[3][0],
        "C44": matrix[3][3],
        "C45": matrix[3][4],
        "C46": matrix[3][5],
        "C55": matrix[4][4],
        "C56": matrix[4][5],
        "C66": matrix[5][5],
    }

    # Replace placeholders with formatted numbers
    for key, val in replacements.items():
        formatted_val = format_fortran_number(val)
        trafo_content = trafo_content.replace(f"{{{key}}}", formatted_val)

    # Write back the updated file
    with open(trafo_path, "w") as f:
        f.write(trafo_content)

    print("trafo.f has been updated with values from Chom.json")

if __name__ == "__main__":
    main()
