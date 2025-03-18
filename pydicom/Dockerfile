FROM pydicom/dicom:v3.6.5

# Install Python 3.8 and create a new environment
RUN conda install -y python=3.8

# Create a new conda environment named "py38"
RUN conda create -n py38 python=3.8 --yes

# Activate the environment and install matplotlib, numpy, and pydicom
RUN /opt/conda/bin/conda run -n py38 conda install -y -c conda-forge pydicom matplotlib numpy

# Set the environment to use Python 3.8
ENV PATH /opt/conda/envs/py38/bin:$PATH