FROM cgal/testsuite-docker:ubuntu 

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive

# Install required packages and tools
RUN apt-get update && \
    apt-get install -y \
    software-properties-common \
    build-essential \
    cmake \
    libgmp-dev \
    libmpfr-dev \
    libcgal-dev \
    libqt5widgets5 \
    libqt5gui5 \
    libqt5core5a \
    libqt5opengl5 \
    libcgal-qt5-dev \
    libqt5opengl5-dev \
    libqt5svg5-dev \
    libqt5x11extras5-dev \
    qtbase5-dev \
    qtchooser \
    qt5-qmake \
    qtbase5-dev-tools \
    tar \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Install GCC 11
RUN add-apt-repository ppa:ubuntu-toolchain-r/test && \
    apt-get update && \
    apt-get install -y gcc-11 g++-11 && \
    update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-11 60 && \
    update-alternatives --install /usr/bin/g++ g++ /usr/bin/g++-11 60

# Create a directory for CGAL examples
#RUN mkdir -p /root/CGAL-5.6.1

# Copy the CGAL examples tarball to the container
COPY CGAL-5.6.1-examples.tar.xz /root/

# Extract the CGAL examples
RUN cd /root && \
    tar -xf CGAL-5.6.1-examples.tar.xz

# Set the working directory
WORKDIR /root/CGAL-5.6.1

# Keep the container running
CMD ["tail", "-f", "/dev/null"]

# BUILD EXAMPLES LIKE THIS
# cd $HOME/CGAL-5.6.1/examples/Triangulation_2 # go to an example directory
# cmake -DCMAKE_BUILD_TYPE=Release . # configure the examples
# make # build the examples







