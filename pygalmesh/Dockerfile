# Use the official Ubuntu 22.04 image as the base image
FROM ubuntu:22.04

# Update package lists and install any needed dependencies
RUN apt-get update && \
    apt-get install -y \
    python3 \
    python3-pip \
    unzip \
    cmake \
    g++ \
    pkg-config \
    libgsl-dev \
    povray \
    libgmp-dev \
    libmpfr-dev \
    libeigen3-dev \
    libcgal-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create a directory for the software and unpack the zip files
RUN mkdir -p /root/Progs
COPY pygalmesh-main.zip /root/

WORKDIR /root/Progs

# Unzip the pygalmesh-main.zip file
RUN unzip /root/pygalmesh-main.zip -d /root/Progs

# Set environment variable for Eigen include path
ENV EIGEN_INCLUDE_DIR=/usr/include/eigen3

# Modify setup.py to include Eigen path
RUN sed -i 's|include_dirs=\[os.environ.get("EIGEN_INCLUDE_DIR", "/usr/include/eigen3/")\]|include_dirs=["/usr/include/eigen3"]|g' /root/Progs/pygalmesh-main/setup.py

# Install pygalmesh
WORKDIR /root/Progs/pygalmesh-main
RUN pip3 install .

# Install tifffile using pip for Python 3
RUN pip3 install tifffile

# Command to run when the container starts
CMD ["tail", "-f", "/dev/null"]




