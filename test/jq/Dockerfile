FROM dlmd/sweet-fuzz

RUN git clone https://github.com/stedolan/jq.git
RUN cd jq/ && git submodule update --init

# Default SRC_DIR is /project, but it can be overridden
# by setting the SRC_DIR environment variable
ENV SRC_DIR=/jq
COPY build.sh /tmp/
RUN autobuild /tmp/build.sh

COPY corpus/ /corpus

