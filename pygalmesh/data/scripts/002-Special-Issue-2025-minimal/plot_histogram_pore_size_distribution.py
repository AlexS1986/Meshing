import numpy as np
import matplotlib.pyplot as plt
import os

def voxel_volume_to_diameter(voxel_counts, voxel_size=60.4):
    """
    Convert voxel volume to effective spherical diameter.
    
    Parameters:
        voxel_counts (np.ndarray): Volume in voxel units
        voxel_size (float): Size of one voxel edge in micrometers

    Returns:
        np.ndarray: Effective diameters in micrometers
    """
    voxel_vol = voxel_size ** 3  # in μm³
    diameters = 2 * ((3 * voxel_counts * voxel_vol) / (4 * np.pi)) ** (1/3)
    return diameters


def plot_pore_histogram(
    file_path,
    output_path,
    use_effective_diameter=True,
    voxel_size=60.4,
    usetex=True,
    figsize=(8, 6),
    xlabel_fontsize=20,
    ylabel_fontsize=20,
    tick_fontsize=18,
    bins=50,
    log_x=True,
    hist_color="skyblue",
    edge_color="black"
):
    # Load and parse data
    data = []
    with open(file_path, 'r') as f:
        for line in f:
            if line.strip() and not line.startswith('#'):
                values = list(map(float, line.strip().split()))
                data.append(values)

    data = np.array(data)
    pore_sizes = data[:, 1]  # Column 1 is Pore_Size (volume in voxels)

    if use_effective_diameter:
        pore_sizes = voxel_volume_to_diameter(pore_sizes, voxel_size)
        xlabel = r'Effective Pore Diameter ($\mu$m)'
    else:
        xlabel = r'Volume in Voxels'

    ylabel = r'Number of Pores at Size'

    # LaTeX settings
    if usetex:
        plt.rcParams.update({
            "text.usetex": True,
            "font.family": "serif",
            "pgf.texsystem": "pdflatex",
            "pgf.rcfonts": False,
        })

    # Plotting
    plt.figure(figsize=figsize)
    bin_edges = np.logspace(np.log10(pore_sizes.min()), np.log10(pore_sizes.max()), bins) if log_x else bins
    plt.hist(pore_sizes, bins=bin_edges, color=hist_color, edgecolor=edge_color)

    if log_x:
        plt.xscale('log')

    plt.xlabel(xlabel, fontsize=xlabel_fontsize)
    plt.ylabel(ylabel, fontsize=ylabel_fontsize)
    plt.tick_params(axis='both', labelsize=tick_fontsize)
    plt.grid(True, which='both', linestyle='--', linewidth=0.5)

    plt.tight_layout()

    # Save
    for ext in ['png', 'pdf', 'pgf']:
        out_path = output_path.replace('.png', f'.{ext}')
        plt.savefig(out_path, bbox_inches='tight')

    plt.close()
    print(f"Saved to: {output_path.replace('.png', '.[png/pdf/pgf]')}")


if __name__ == "__main__":
    specimen = "JM-25-19"
    filename = "Pore_Data.txt"
    file_path = os.path.join("/data", "resources", "special_issue_hannover", "raw_dicom", specimen, filename)
    output_file = os.path.join(".", f"{specimen}_pore_histogram.png")

    plot_pore_histogram(
        file_path=file_path,
        output_path=output_file,
        use_effective_diameter=True,
        voxel_size=60.4,
        usetex=True,
        figsize=(8, 6),
        xlabel_fontsize=20,
        ylabel_fontsize=20,
        tick_fontsize=18,
        bins=50,
        log_x=True,
        hist_color="skyblue",
        edge_color="blue"
    )