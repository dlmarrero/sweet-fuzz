# sweet-fuzz
A suite of fuzzing tools and some glue code that simplifies using them.

## Installation
Just pull the latest image from dockerhub:
```
docker pull dlmd/sweet-fuzz
```

Alternatively, you can build the Dockerfile in this repo.

## Building a fuzz harness
sweet-fuzz provides an `autobuild` command in the container's `PATH`. This script will create three builds:
1. A debug build (`-O0 -g -ggdb`)
2. A fuzzer build (`CC=afl-clang-fast CXX=afl-clang++-fast`)
3. A coverage build (`-fprofile-args -ftest-coverage`)

The most surefire way to ensure the builds run successfully, provide `autobuild` with a shell script that builds your target. An example Dockerfile might look like this:
```docker
FROM dlmd/sweet-fuzz
COPY my_src/ /project/
COPY my_build_script.sh /tmp/
RUN autobuild /tmp/my_build_script.sh
```

### Directory structure and enviornment variables
The easiest way to use sweet-fuzz is to stick to the following conventions:
* The source code for your target should be in `/project`
* The fuzz corpus should be in `/corpus`
* When fuzzing begins, your fuzz output will be written to `/fuzz_out`

If necessary, you can override the directory containing your project with the environment variable `SRC_DIR`. For example:
```docker
FROM dlmd/sweet-fuzz
COPY my_src/ /my_src
ENV SRC_DIR=/my_src
RUN autobuild /my_src/build.sh
```

You may also find it necessary to use a different compiler for the fuzzer build (e.g. the project fails to build with clang). You can override the fuzzer compiler by setting the environment variables `FUZZ_CC` and `FUZZ_CXX`
```docker
FROM dlmd/sweet-fuzz
COPY my_src/ /project
ENV FUZZ_CC=afl-gcc
ENV FUZZ_CXX=afl-g++
RUN autobuild /my_src/build.sh
```

## Running a fuzz harness
When running your fuzz harness container, map a port from your host to container port 8000 to be able to view the coverage report. You may also want to mount a directory from your host to the `/fuzz_out` directory in the container so your results are not list. Here is an example command that will mount the fuzzer output to your host at `/dev/shm/my_tgt`.

```docker
docker run -it -p 8000:8000 -v /dev/shm/my_tgt:/fuzz_out my_tgt -- fuzz -j3 -vv --exec ./my_tgt_bin -abc @@
```

sweet-fuzz provides a `fuzz` command in the container's `PATH`. The most important switches are `-j` and `--exec`. When providing the command-line for running your target, the path to the binary **MUST** be relative to `SRC_DIR`. For example, if your binary is located at `/project/my_tgt` and reads from a file, then your `--exec` argument should be `./my_tgt @@`. Here are all the options for the `fuzz` command:
```
usage: fuzz.py [ options ] [ add'l afl-fuzz args ] --exec target_cmdline 

Required parameters:
  --exec        - command-line args for target.
                  path to binary must be relative to project root dir

Optional afl-fuzz parameters:
  -i dir        - input directory with test cases (/corpus)
  -o dir        - output directory for fuzzer findings (/fuzz_out)
  -j num        - number of afl-fuzz instances to run in master/slave mode (nproc / 2)
  --fuzz-dir    - absolute path to root of fuzz build
    
  Other afl-fuzz parameters not listed can just be added to the arguments list.
  For example, "fuzz.py -x dictionary.txt --exec ./the_bin @@" is valid.

Optional afl-cov parameters:
  --cov-dir     - absolute path to root of code coverage build (/*-cov)
  --port        - web port for serving the code coverage report

Other stuff:
  -v            - increase verbosity [-v = INFO, -vv = DEBUG]
```

A single `-v` will log new function coverage. `-vv` will log new line coverage.

## TODO
- [ ] Add a `gprof` build option to troubleshoot slow harnesses with profiling data

