# Notes on fuzzing networked bins

## Improving Tooling
### Creating a Docker container with a suite of tools
**Problem:** Having to manually manage compilation, multiprocessor fuzzing, and coverage collection is tedious.
**Solution:** Create a Docker container which can: 
1. Automatically recognize common build systems
2. Create a fuzzer/coverage/standard build
3. Easily start a multiprocess fuzz job
4. Expose coverage information

#### Requirements
* Create a script aliased to the command `autobuild` which will attempt to determine the build system in use and build the project accordingly. The script will build three versions of the project:
	1. Fuzzer build using AFL/libFuzzer
	2. Coverage build for use with afl-cov
	3. Normal build for debugging and triage
* Create a script which wraps the standard `afl-fuzz` command to provide a `-j` switch for starting multiple instances of afl++. It should use the mix of exploration strategies mentioned in the afl++ docs for multiprocess fuzzing.
* When fuzzing begins, it should spawn a webserver that serves up the code coverage reports from `afl-cov`. A nice-to-have (n2h) would be for the page to hot-reload when new coverage is found.
* The Docker container should be able to start in detached mode (`-dt`) and the user should be able to get updates from `afl-fuzz` and `afl-cov` by running `docker logs <id>`
* Another n2h would be to expose the generated .cov files to allow easily ingesting them into a tool like [bncov](https://github.com/ForAllSecure/bncov) for lower-level coverage analysis.
* n2h - Should cache which build steps have successfully completed, so that if a later step fails you can pick up where you left off
	* This may not be valuable enough to implement since this is mostly going to run in a Docker container
	* A commandline argument might do the trick

#### TODO
* Start afl-cov/server thread in fuzz runner
* Tweak exploration modes on M/S instances of afl-fuzz
* Would also be cool to integrate ikos
* Try to get clang 9 so we can use LTO collision free llvm_mode

