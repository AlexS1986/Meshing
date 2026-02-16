import os
import pandas as pd
import matplotlib

# Use non-interactive backend
matplotlib.use("Agg")

import matplotlib.pyplot as plt


def load_ebsd_grain_data(filepath):
    columns = [
        "grain_id",
        "phase",
        "phi1_deg", "PHI_deg", "phi2_deg",
        "phi1_rad", "PHI_rad", "phi2_rad",
        "h", "k", "l", "u", "v", "w",
        "h_f", "k_f", "l_f", "u_f", "v_f", "w_f",
        "x_um", "y_um",
        "IQ",
        "CI",
        "fit_deg",
        "video_signal",
        "R", "G", "B",
        "edge_grain",
        "n_points",
        "area_um2",
        "diameter_um",
        "ASTM_grain_size",
        "aspect_ratio",
        "major_axis_radius_um",
        "minor_axis_radius_um",
        "ellipse_orientation_deg",
        "ellipticity",
        "circularity",
        "max_feret",
        "min_feret",
        "avg_orientation_spread",
        "avg_neighbor_misorientation"
    ]

    return pd.read_csv(
        filepath,
        comment="#",
        delim_whitespace=True,
        header=None,
        names=columns
    )

def save_histogram(
    df,
    column,
    script_dir,
    bins=20,
    filename=None,
    xlabel=None,
    title=None,
    positive_only=True,
    xlim=None
):
    """
    Save a histogram of a chosen EBSD grain data column.

    Parameters
    ----------
    df : pandas.DataFrame
        EBSD grain dataframe
    column : str
        Column name to plot
    script_dir : str
        Directory where the script lives (output location)
    bins : int, optional
        Number of histogram bins
    filename : str, optional
        Output filename (auto-generated if None)
    xlabel : str, optional
        X-axis label
    title : str, optional
        Plot title
    positive_only : bool, optional
        Remove non-positive values (recommended for size metrics)
    xlim : tuple(float, float), optional
        (xmin, xmax) range for x-axis
    """

    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found in DataFrame")

    # Remove anti-grains
    df_plot = df[df["grain_id"] > 0]

    # Remove invalid values if requested
    if positive_only:
        df_plot = df_plot[df_plot[column] > 0]

    # Apply x-range filtering if requested
    if xlim is not None:
        xmin, xmax = xlim
        df_plot = df_plot[
            (df_plot[column] >= xmin) &
            (df_plot[column] <= xmax)
        ]

    if df_plot.empty:
        raise ValueError(f"No valid data to plot for column '{column}'")

    # Auto-generate filename
    if filename is None:
        filename = f"{column}_histogram.png"

    output_path = os.path.join(script_dir, filename)

    # Plot
    plt.figure(figsize=(7, 5))
    plt.hist(
        df_plot[column],
        bins=bins,
        edgecolor="black"
    )

    plt.xlabel(xlabel if xlabel else column)
    plt.ylabel("Number of Grains")
    plt.title(title if title else f"{column} Distribution")

    if xlim is not None:
        plt.xlim(xlim)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()

    print(f"Histogram saved to: {output_path}")


# ------------------ main ------------------

# Directory where this script lives
script_dir = os.path.dirname(os.path.abspath(__file__))

# Data folder
data_dir = os.path.join(script_dir, "data_c04")

# Input file
file_path = os.path.join(
    data_dir, "Grain_Info_WAAM316L_Vertical-1.txt"
)

# Output figure
output_path = os.path.join(
    script_dir, "ASTM_grain_size_histogram.png"
)

# Load data
df = load_ebsd_grain_data(file_path)

# Remove anti-grains and invalid ASTM values
df_clean = df[
    (df["grain_id"] > 0) &
    (df["ASTM_grain_size"] > 0)
]

save_histogram(
    df=df,
    column="area_um2",
    script_dir=script_dir,
    bins=25,
    xlabel="Grain Area (µm^2)",
    title="Grain Size Distribution",
    xlim=(300,20000)
)

