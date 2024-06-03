import numpy as np
from collections import deque, Counter


# File path
file_path = '/data/02_voxel2mesh/read_and_mesh_scans/resources/data_small/hypo_test_128.dat'

# Read the data from the file
with open(file_path, 'r') as file:
    # Read all lines and split by spaces to get individual elements
    data = file.read().split()

# Convert data to integers
data = list(map(int, data))

# Convert the list to a NumPy array and reshape to 128x128x128
array_3d = np.array(data).reshape((128, 128, 128))

# array_3d is now a 3D NumPy array of shape (128, 128, 128)
print(array_3d.shape)  # Should print (128, 128, 128)


num_points = 8  # Change this to the desired number of points along each axis

# Generate evenly spaced indices along each axis
indices = np.linspace(0, 127, num_points, dtype=int)

# Create a list of coordinates from the indices
coordinates = [(i, j, k) for i in indices for j in indices for k in indices]


# array_out = np.copy(array_3d)

# Define the flood fill function
def flood_fill(array, start_coords, cell_number_pore, cell_number_material):
    
    
    
    
    x, y, z = start_coords
    array_out = np.copy(array)
    initial_value_at_seedpoint = array[x, y, z]
    
    has_been_visited_at_different_seed = initial_value_at_seedpoint not in [0,1]
    out_cell_number_material = cell_number_material
    out_cell_number_pore = cell_number_pore
    
    if has_been_visited_at_different_seed:
        return array_out, out_cell_number_material, out_cell_number_pore
        
    visited = np.zeros_like(array, dtype=bool)
    queue = deque([start_coords])
    
    directions = [
        (1, 0, 0), (-1, 0, 0),
        (0, 1, 0), (0, -1, 0),
        (0, 0, 1), (0, 0, -1)
    ]
    while queue:
        cx, cy, cz = queue.popleft()
        
        if visited[cx, cy, cz]:
            continue
        
        visited[cx, cy, cz] = True
        
        if(array_out[cx,cy,cz] == 1):
            array_out[cx,cy,cz] = cell_number_material
            out_cell_number_material = cell_number_material + 2
        elif(array_out[cx,cy,cz] == 0):
            array_out[cx,cy,cz] = cell_number_pore
            out_cell_number_pore = cell_number_pore + 2
        
        # add other neighbors
        for dx, dy, dz in directions:
            nx, ny, nz = cx + dx, cy + dy, cz + dz
            
            if 0 <= nx < 128 and 0 <= ny < 128 and 0 <= nz < 128:
                if not visited[nx, ny, nz] and array[nx, ny, nz] == initial_value_at_seedpoint: 
                    queue.append((nx, ny, nz))
    
    return array_out, out_cell_number_material, out_cell_number_pore




# Print the coordinates
n = 1
cell_number_pore = 2
cell_number_material = 3

for coord in coordinates:
    print(f"Running Seed Point {coord} number {n} out of {len(coordinates)}")

    
    array_3d,  cell_number_material, cell_number_pore, = flood_fill(array_3d,coord,cell_number_pore,cell_number_material)
    
    # cell_number_pore = cell_number_pore + 2
    # cell_number_material = cell_number_material+ 2    
    n = n+1
    


indices_0 = np.argwhere(array_3d == 0)
indices_1 = np.argwhere(array_3d == 1)
combined_indices = np.vstack((indices_0, indices_1))

array_zero_or_one = array_3d[tuple(combined_indices.T)]

count_ones = np.count_nonzero(array_3d == 1)
print(f"Number of 1s in array_3d: {count_ones}")



def check_and_update_point(array, x, y, z):
    array_out = np.copy(array)
    initial_value = array_out[x, y, z]
    
    # Define neighborhood directions
    directions = [
        (1, 0, 0), (-1, 0, 0),
        (0, 1, 0), (0, -1, 0),
        (0, 0, 1), (0, 0, -1)
    ]
    
    # Collect neighbor values
    neighbor_values = []
    for dx, dy, dz in directions:
        nx, ny, nz = x + dx, y + dy, z + dz
        if 0 <= nx < array_out.shape[0] and 0 <= ny < array_out.shape[1] and 0 <= nz < array_out.shape[2]:
            neighbor_values.append(array_out[nx, ny, nz])
    
    # Check if there are neighbors with the same value
    if initial_value in neighbor_values:
        return array_out
    
    # Count occurrences of each value in the neighbors
    value_counts = Counter(neighbor_values)
    majority_value, majority_count = value_counts.most_common(1)[0]
    
    # Check if there is a majority value
    if len(value_counts) > 1 and majority_count == value_counts.most_common(2)[1][1]:
        # No clear majority, select one of the neighbor values randomly
        array_out[x, y, z] = np.random.choice(neighbor_values)
    else:
        # Set the value to the majority value
        array_out[x, y, z] = majority_value
        
    return array_out

for x,y,z in combined_indices:
    array_3d = check_and_update_point(array_3d,x, y, z)

count_ones = np.count_nonzero(array_3d == 1)
print(f"Number of 1s in array_3d: {count_ones}")

n = 1
for coord in combined_indices:
     #test = array_out[coord[0], coord[1], coord[2]]
     print(f"Running Seed Point {coord} number {n} out of {len(combined_indices)}")
     array_3d,  cell_number_material, cell_number_pore, = flood_fill(array_3d,coord,cell_number_pore,cell_number_material)
    
     # cell_number_pore = cell_number_pore + 2
#     # cell_number_material = cell_number_material+ 2    
#     n = n+1
    

print(np.max(array_3d))
print(np.min(array_3d))


flat_array = array_3d.flatten()
# line = ' '.join(map(str, flat_array))


unique_values = np.unique(array_3d)
num_unique_values = len(unique_values)

print(f"Unique values in array_3d: {unique_values}")
print(f"Number of unique values in array_3d: {num_unique_values}")

# Write the line to a file
with open('/data/02_voxel2mesh/read_and_mesh_scans/resources/data_small/output_file.dat', 'w') as file:
        for i in range(0, len(flat_array), 128):
            line = ' '.join(map(str, flat_array[i:i+128]))
            file.write(line + '\n')
print("File 'output_file.txt' has been created.")


# If you need to access elements, you can now use array_3d[x, y, z]
