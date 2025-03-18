import numpy as np
import os
from scipy.linalg import lu_factor, lu_solve
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from scipy.spatial import ConvexHull
from scipy.spatial import Delaunay


script_path = os.path.dirname(__file__)

# Constants
pi = np.pi

# Input stiffness matrix (C in Voigt notation)
cmat = np.array([
    [3.08e5, 0.69e5, 0.69e5, 0, 0, 0],
    [0.69e5, 3.08e5, 0.69e5, 0, 0, 0],
    [0.69e5, 0.69e5, 3.08e5, 0, 0, 0],
    [0, 0, 0, 0.36e5, 0, 0],
    [0, 0, 0, 0, 0.36e5, 0],
    [0, 0, 0, 0, 0, 0.36e5]
])

# cmat = np.array([
#     [2.465e5, 1.473e5, 1.473e5, 0, 0, 0],
#     [1.473e5, 2.465e5, 1.473e5, 0, 0, 0],
#     [1.473e5, 1.473e5, 2.465e5, 0, 0, 0],
#     [0, 0, 0, 1.247e5, 0, 0],
#     [0, 0, 0, 0, 1.247e5, 0],
#     [0, 0, 0, 0, 0, 1.247e5]
# ])


# Function to compute the inverse of a 6x6 matrix
def invmat66(mat):
    """ Compute the inverse of a 6x6 matrix using LU decomposition. """
    lu, piv = lu_factor(mat)
    return lu_solve((lu, piv), np.eye(6))

# Function to compute transformation matrix
def trafo(phi1, phi2):
    """ Compute transformation matrix for given angles phi1 and phi2. """
    c1, c2 = np.cos(phi1), np.cos(phi2)
    s1, s2 = np.sin(phi1), np.sin(phi2)

    amat = np.array([
        [c1, s1 * c2, s1 * s2],
        [-s1, c1 * c2, c1 * s2],
        [0, -s2, c2]
    ])
    return amat

# Compute compliance matrix (S = C⁻¹)
smat = invmat66(cmat)

# Save matrices
np.savetxt(os.path.join(script_path,"c_tensor.txt"), cmat, fmt="%.5e")
np.savetxt(os.path.join(script_path,"s_tensor.txt"), smat, fmt="%.5e")

# Parameters
lmax, mmax = 200, 100
emodul_results = []
gmodul_results = []

# Loop over angles
for m in range(mmax + 1):
    phi1 = pi / mmax * m
    for l in range(lmax + 1):
        phi2 = 2.0 * pi / lmax * l

        # Compute transformation matrix
        amat = trafo(phi1, phi2)

        # Compute transformation tensors (Voigt notation)
        tmate = np.zeros((6, 6))
        tmats = np.zeros((6, 6))

        for i in range(3):
            for j in range(3):
                tmate[i, j] = amat[i, j] ** 2
                tmats[i, j] = amat[i, j] ** 2
            for j in range(3, 6):
                tmate[i, j] = amat[i, j - 3] * amat[i, j - 3]
                tmats[i, j] = 2 * amat[i, j - 3] * amat[i, j - 3]

        for i in range(3, 6):
            for j in range(3, 6):
                tmate[i, j] = amat[i - 3, j - 3] * amat[i - 3, j - 3] + amat[i - 3, j - 3] * amat[i - 3, j - 3]
                tmats[i, j] = amat[i - 3, j - 3] * amat[i - 3, j - 3]

        # Compute inverse of tmats
        try:
            itmats = invmat66(tmats)
        except Exception as e:
            print(f"Error in matrix inversion for m={m}, l={l}: {e}")
            continue  # Skip this iteration if the matrix inversion fails

        # Compute new compliance matrix
        hilf = smat @ itmats
        smatneu = tmate @ hilf

        # Compute Young’s modulus
        try:
            emod = 1.0 / smatneu[0, 0]
            if np.isfinite(emod):  # Check if emod is finite
                e = np.array([np.cos(phi1) * emod, np.sin(phi1) * np.cos(phi2) * emod, np.sin(phi1) * np.sin(phi2) * emod])
                emodul_results.append(e)
        except Exception as e:
            print(f"Error in computing Young's modulus for m={m}, l={l}: {e}")

        # Compute shear modulus
        try:
            gmod = np.sqrt(2.0) / np.sqrt(smatneu[4, 4] ** 2 + smatneu[5, 5] ** 2 + 2.0 * smatneu[4, 5] ** 2)
            if np.isfinite(gmod):  # Check if gmod is finite
                g = np.array([np.cos(phi1) * gmod, np.sin(phi1) * np.cos(phi2) * gmod, np.sin(phi1) * np.sin(phi2) * gmod])
                gmodul_results.append(g)
        except Exception as e:
            print(f"Error in computing shear modulus for m={m}, l={l}: {e}")

# Convert results to numpy arrays to save
emodul_results = np.array(emodul_results)
gmodul_results = np.array(gmodul_results)

# Save results
np.savetxt(os.path.join(script_path, "emodul.plt"), emodul_results, fmt="%.15e %.18e %.18e")
np.savetxt(os.path.join(script_path, "gmodul.plt"), gmodul_results, fmt="%.15e %.18e %.18e")

print("Computation complete. Results saved to files.")



# Load E-modulus data (x, y, z)
emodul_data1 = np.loadtxt(os.path.join(script_path, "emodul-mgzro2.plt"))
emodul_data = np.loadtxt(os.path.join(script_path, "emodul.plt"))

# Compare the arrays element-wise and find where they differ
difference = emodul_data1 != emodul_data
# Find the indices of the differing elements
differing_indices = np.where(difference)

# Remove rows with NaN values (if needed, but it's commented out here)
# emodul_data = emodul_data[~np.isnan(emodul_data).any(axis=1)]

# Extract coordinates
X, Y, Z = emodul_data[:, 0], emodul_data[:, 1], emodul_data[:, 2]

# Create 3D figure
fig = plt.figure(figsize=(10, 7))
ax = fig.add_subplot(111, projection="3d")

# Scatter plot for better visualization of discrete points
ax.scatter(X, Y, Z, c=Z, cmap="viridis", marker="o")

# Combine X, Y, Z into a single array for Delaunay triangulation in 3D
points = np.unique(np.column_stack((X, Y, Z)), axis=0)

# Perform Delaunay Triangulation in 3D
tri = Delaunay(points)  # Delaunay triangulation in 3D using X, Y, and Z

# Plot the surface from the 3D Delaunay triangulation
for simplex in tri.simplices:
    x = points[simplex, 0]
    y = points[simplex, 1]
    z = points[simplex, 2]
    
    # Create a surface plot for each triangle
    ax.plot_trisurf(x, y, z, color='lightblue', alpha=0.5, linewidth=0.5, edgecolors='k')

# Labels and title
ax.set_xlabel("X-axis")
ax.set_ylabel("Y-axis")
ax.set_zlabel("E-Modulus")
ax.set_title("3D Surface from Delaunay Triangulation of E-Modulus")

# Save the figure to a file
plt.savefig(os.path.join(script_path, "emodul_delaunay_plot_3d.png"), dpi=300, bbox_inches="tight")
plt.close()  # Close the plot to avoid interactive display

print("Plot saved as 'emodul_delaunay_plot_3d.png'.")