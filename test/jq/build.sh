set -e
autoreconf -fi
./configure --with-oniguruma=builtin --disable-maintainer-mode
make -j`nproc`

