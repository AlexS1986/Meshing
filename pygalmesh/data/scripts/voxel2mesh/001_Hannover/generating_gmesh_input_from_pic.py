import numpy as np
from PIL import Image
import matplotlib.pyplot as plt

#-------------------------------------------------------------------------#
# Binary image to Boundary spline Gmsh code
#-------------------------------------------------------------------------#

# Step 1: Load and process the image
image = Image.open('/data/resources/2D_image_for_gmsh/OM.bmp')
image_bw = image.convert('1')  # Convert image to black and white

# Step 2: Fill holes in the binary image
I = np.array(image_bw)  # Convert to numpy array
I_fill = np.copy(I)
I_fill[~I] = 1  # Fill the holes (invert)
I_fill[I] = 0  # Fill the holes (invert)

# Step 3: Find the boundary of the filled binary image
from skimage.measure import find_contours

contours = find_contours(I_fill, 0.5)

# Assume we're dealing with the first contour
b = contours[0]  # boundary points

# Downsample boundary points
c1 = b[:, 1][::1]  # x-coordinates (downsample)
c2 = b[:, 0][::1]  # y-coordinates (downsample)

# Step 4: Prepare GMSH input data
NyI, NxI = I.shape
cl_1 = 100
cl_2 = 5

# Domain extent
xmin = 1
xmax = NxI
ymin = 1
ymax = NyI

# Step 5: Write GMSH file
with open('mesh.txt', 'w') as file:
    # Mesh size and boundary information
    file.write(f'\n// mesh size description\n')
    file.write(f'cl_1   =  {cl_1};\n')
    file.write(f'cl_2   =  {cl_2};\n')
    
    # Boundary points
    file.write(f'\n// boundary points that forms Rhizotron\n')
    file.write(f'Point(1) = {{ {xmin}, {ymin}, 0, cl_1 }};\n')
    file.write(f'Point(2) = {{ {xmax}, {ymin}, 0, cl_1 }};\n')
    file.write(f'Point(3) = {{ {xmax}, {ymax}, 0, cl_1 }};\n')
    file.write(f'Point(4) = {{ {xmin}, {ymax}, 0, cl_1 }};\n')

    # Lines that connect boundary points
    file.write(f'\n// lines that connect boundary\n')
    file.write(f'Line(1) = {{1, 2}};\n')
    file.write(f'Line(2) = {{2, 3}};\n')
    file.write(f'Line(3) = {{3, 4}};\n')
    file.write(f'Line(4) = {{4, 1}};\n')
    file.write(f'Line Loop(4) = {{1, -2, -3, -4}};\n')

    # Mesh parameters
    file.write(f'\n// Mesh Parameters\n')
    file.write(f'Mesh.CharacteristicLengthExtendFromBoundary = 0;\n')
    file.write(f'Mesh.CharacteristicLengthMax = 25;\n')

    # Define segment coordinates
    file.write(f'\n// Define Segment coordinates\n')
    X = ','.join(map(str, c1))
    Y = ','.join(map(str, c2))
    file.write(f'X = {{ {X} }};\n')
    file.write(f'Y = {{ {Y} }};\n')

    # Define spline surface
    file.write(f'\n// Define spline surface\n')
    file.write(f'LN = 90;\n')
    file.write(f'nR = #X[ ];\n')
    file.write(f'p0 = newp;\n')
    file.write(f'p = p0;\n')
    file.write(f'For i In {{0:nR-1}}\n')
    file.write(f'    Point(newp) = {{ X[i], Y[i], 0, cl_2 }};\n')
    file.write(f'EndFor\n')
    file.write(f'p2 = newp - 1;\n')
    file.write(f'BSpline(90) = {{ p:p2,p }};\n')
    file.write(f'Line Loop(91) = {{ 90 }};\n')
    file.write(f'Plane Surface(92) = {{ 91 }};\n')
    file.write(f'Plane Surface(93) = {{ 4,91 }};\n')

# Step 6: Save the contour boundary as a picture
plt.plot(c1, c2, 'r-', linewidth=2)
plt.gca().set_aspect('equal', adjustable='box')

# Save the plot as an image file
plt.savefig('contour_boundary.png', dpi=300)

# Optionally, you can close the plot to avoid it showing up in the notebook or console
plt.close()
