FROM bitnami/minideb

# Install build tools, afl++ dependencies, and common utilities
# TODO install clang >= 9 to get afl-clang-lto (collision free coverage)
ENV DEBIAN_FRONTEND=noninteractive
RUN install_packages build-essential automake autoconf libtool cmake vim git \
	ca-certificates libtool-bin python3 bison libglib2.0-dev \
	libpixman-1-dev python-setuptools gcc-multilib g++-multilib wget \
	flex afl-cov llvm llvm-dev clang

# Build latest stable version of afl++
RUN git clone https://github.com/AFLplusplus/AFLplusplus
RUN cd AFLplusplus && make -j`nproc` distrib && make install

# Bring in scripts and add them to the path
COPY src/ /sweet-fuzz/
ENV SWEET_SRC=/sweet-fuzz
ENV PATH="${PATH}:${SWEET_SRC}"

