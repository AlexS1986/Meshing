import matplotlib.pyplot as plt
import numpy as np
import pydicom
import pydicom.dataset
from pydicom import dcmread
import os

# https://zenodo.org/records/5887359
script_path = os.path.dirname(__file__)
file_path = os.path.join(script_path,"resources","dicom_breast","IN_00002.dcm")

ds : pydicom.dataset.FileDataset = dcmread(file_path)



scan_intensity_as_array = np.array(ds.pixel_array)
min = scan_intensity_as_array.min()
max = scan_intensity_as_array.max()

plt.imshow(ds.pixel_array, cmap=plt.cm.gray)

output_path = os.path.join(script_path, "dicom_image2.png")
plt.savefig(output_path)

# Optionally, close the plot to free up memory
plt.close()
