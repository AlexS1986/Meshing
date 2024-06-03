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

# Set environment variables if needed
# ENV MY_VAR=my_value

# Create a directory for the software and unpack the zip files
RUN mkdir -p /root/Progs
COPY neper-main.zip /root/
COPY gmsh-4.12.2-source.tgz /root/

# Extract Neper and Gmsh archives
RUN unzip /root/neper-main.zip -d /root/Progs/
RUN tar -xzf /root/gmsh-4.12.2-source.tgz -C /root/Progs/

# Install Gmsh
WORKDIR /root/Progs/gmsh-4.12.2-source
RUN mkdir -p build && cd build && cmake .. && make && make install

# Compile Neper
WORKDIR /root/Progs/neper-main/src
RUN mkdir -p build && cd build && cmake .. && make && make install

# Install tifffile using pip for Python 3
RUN pip3 install tifffile

# Command to run when the container starts
CMD ["tail", "-f", "/dev/null"]



