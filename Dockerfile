# Need sid so we can get gcc-9
FROM debian:sid-slim

ARG PROJECT_DIR=/project/
ARG OUTPUT_DIR=/fuzz_out/
ARG CORPUS_DIR=/corpus/
ARG SWEET_SRC_DIR=/sweet-src/

# Set the shell to bash
SHELL ["/bin/bash", "-c"]

# Make sure up-to-date
RUN apt-get update && apt-get upgrade -y

# Install common utilities
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get install -y \
    wget curl vim git procps ca-certificates gnupg

# Now to get llvm-11, we need to add the development branch
RUN curl https://apt.llvm.org/llvm-snapshot.gpg.key | apt-key add -
RUN echo 'deb http://apt.llvm.org/unstable/ llvm-toolchain main' >> /etc/apt/sources.list.d/llvmsource.list
RUN echo 'deb-src http://apt.llvm.org/unstable/ llvm-toolchain main' >> /etc/apt/sources.list.d/llvmsource.list

# Now update package list for llvm-11
RUN apt-get update

# Install build tools and afl++ dependencies
RUN apt-get install -y \
    build-essential automake autoconf libtool libtool-bin cmake \
    gcc-10-multilib g++-10-multilib gcc-10-plugin-dev \
    clang-11 llvm-11 llvm-11-dev \
    libglib2.0-dev libpixman-1-dev \
	python3 python3-dev python-setuptools \
    bison flex lcov

# Now symlink llvm-11
RUN ln -s /usr/bin/clang-11 /usr/bin/clang
RUN ln -s /usr/bin/clang++-11 /usr/bin/clang++
RUN ln -s /usr/bin/llvm-config-11 /usr/bin/llvm-config

# Clone into afl-cov because it's not in sid repos
WORKDIR /tmp
RUN git clone https://github.com/mrash/afl-cov
RUN cp afl-cov/afl-cov /usr/local/bin
RUN rm -rf afl-cov

# Build latest stable version of afl++
WORKDIR /
RUN git clone https://github.com/AFLplusplus/AFLplusplus
RUN cd AFLplusplus && make -j`nproc` distrib && make install

# Now setup volumes to improve speed by using "real" file-systems
VOLUME $PROJECT_DIR
VOLUME $OUTPUT_DIR
VOLUME $CORPUS_DIR
VOLUME $SWEET_SRC_DIR

# Bring in scripts and add them to the path
COPY src/ $SWEET_SRC_DIR

# Setup environment variables
ENV SRC_DIR=$PROJECT_DIR
ENV SWEET_SRC=$SRC_DIR
ENV PATH="${PATH}:${SWEET_SRC}"
