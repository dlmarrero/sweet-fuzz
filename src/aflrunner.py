#!/usr/bin/env python3.7
import logging
import subprocess
import threading
import argparse
import sys
import os
from copy import deepcopy
from utils import *

# TODO how to properly manage loggers without messing with the root logger?
# TODO minimize corpus on keyboard interrupt
logging.basicConfig(level=logging.WARNING, format="%(asctime)s | %(name)s | %(message)s",
                    datefmt='%Y-%d-%m %H:%M:%S')


def get_nproc():
    proc = subprocess.run("nproc", capture_output=True)
    return int(proc.stdout.decode())


def run_afl_instance(cpu_id: int, afl_args, cmdline: list, master=False):
    """
    Runs an instance of AFL

    :param cpu_id: Numeric CPU identifier supplied to taskset -c option
    :param cmdline: Arguments to be passed to afl-fuzz
    :param master: True if AFL instance should be run as master (-M). Defaults to slave mode (-S)
    :return: None
    """
    logger = logging.getLogger("FUZZ-%02d" % cpu_id)

    # Set up the arguments to run afl-fuzz in master/slave with specific power schedules on specific CPUs
    run_args = [ "taskset", "-c", str(cpu_id) ]             # Force AFL instance to run on a specific CPU
    run_args += [ "/usr/local/bin/afl-fuzz", *afl_args ]    # Additional afl-fuzz args

    # Set up power schedules for master/slaves based on afl++ recomendations:
    # https://github.com/AFLplusplus/AFLplusplus/blob/master/docs/power_schedules.md
    instance_id = "fuzz_%02d" % cpu_id
    slave_schedules = [ 'coe', 'fast', 'explore' ]          # recommended power scheds for slaves
    if master:
        schedule = 'exploit'
        run_args += [ '-M', instance_id, '-p', schedule ]
    else:
        # Select slave's power schedule in a round-robin fashion based on CPU id
        assert cpu_id != 0  # Only the master instance should ever have cpu id 0
        schedule = slave_schedules[cpu_id % len(slave_schedules)]
        run_args += [ '-S', instance_id, '-p', schedule ]

    # Finally, tack on the target's cmdline
    run_args += [ "--", *cmdline ]

    # Launch the afl-fuzz instance
    logger.info("Starting %s afl-fuzz instance (power schedule: %s)" % ("master" if master else "slave", schedule))
    proc = subprocess.Popen(run_args, stdout=subprocess.PIPE, env={"AFL_NO_AFFINITY": '1'})

    # Monitor instance output
    crash_count = 0
    testcase_count = 0
    for line in iter(proc.stdout.readline, b""):
        line = line.decode().strip()

        # Log line at the appropriate level
        if "uniq crashes found" in line:
            # If line reports new unique crashes or new test cases, log as CRITICAL. Else DEBUG
            n_crashes = int(line[line.find(" uniq crashes found") - 1])
            n_testcases = int(line[line.find(" total") - 1])
            if n_crashes != crash_count:
                logger.critical(line)
                crash_count = n_crashes
            elif n_testcases != testcase_count:
                logger.info(line)
                testcase_count = n_testcases
            else:
                logger.debug(line)
        elif "Entering queue cycle" in line:
            logger.info(line)
        elif "PROGRAM ABORT" in line or "Location" in line:
            # afl-fuzz instance failed to start
            logger.critical(line)
        else:
            logger.debug(line)

    # Wait for process to exit and check return code
    proc.wait()
    if proc.returncode != 0:
        # TODO signal to other threads that things have gone wrong (specifcally afl-cov)
        logger.critical("AFL instance returned non-zero exit code: %d" % proc.returncode)
        logger.critical("Failed command: %s" % " ".join(run_args))


def start_afl_instances(num_instances: int, afl_args, cmdline: list):
    """
    Starts for afl-fuzz instance threads
    :param num_instances: Number of afl-fuzz instances to start
    :param cmdline: Command-line for running the target
    :return: None
    """
    logger = logging.getLogger('AFL-DIST')
    logger.warning("Starting %d afl-fuzz instances in distributed mode" % num_instances)

    threads = list()

    # Start master instance
    cpu_id = 0
    thread = threading.Thread(target=run_afl_instance, args=(cpu_id, afl_args, cmdline, True))
    thread.start()
    threads.append(thread)

    # Start slave instances. Valid CPU IDs for taskset do not include 0
    for cpu_id in range(1, num_instances):
        thread = threading.Thread(target=run_afl_instance, args=(cpu_id, afl_args, cmdline))
        thread.start()
        threads.append(thread)

    return threads


def init_parser(add_help=True):
    parser = argparse.ArgumentParser(
        add_help=add_help,
        # This mirrors the usage from afl++
        usage="""%(prog)s [ options ] -- /path/to/fuzzed_app [ ... ]

Required parameters:
  -i dir        - input directory with test cases
  -o dir        - output directory for fuzzer findings

Execution control settings:
  -p schedule   - power schedules recompute a seed's performance score.
                  <explore(default), fast, coe, lin, quad, exploit, mmopt, rare>
                  see docs/power_schedules.md
  -f file       - location read by the fuzzed program (stdin)
  -t msec       - timeout for each run (auto-scaled, 50-1000 ms)
  -m megs       - memory limit for child process (50 MB)
  -Q            - use binary-only instrumentation (QEMU mode)
  -U            - use unicorn-based instrumentation (Unicorn mode)
  -W            - use qemu-based instrumentation with Wine (Wine mode)

Mutator settings:
  -R[R]         - add Radamsa as mutator, add another -R to exclusivly run it
  -L minutes    - use MOpt(imize) mode and set the limit time for entering the
                  pacemaker mode (minutes of no new paths, 0 = immediately).
                  a recommended value is 10-60. see docs/README.MOpt.md
  -c program    - enable CmpLog by specifying a binary compiled for it.
                  if using QEMU, just use -c 0.

Fuzzing behavior settings:
  -N            - do not unlink the fuzzing input file (only for devices etc.!)
  -d            - quick & dirty mode (skips deterministic steps)
  -n            - fuzz without instrumentation (dumb mode)
  -x dir        - optional fuzzer dictionary (see README.md, its really good!)

Testing settings:
  -s seed       - use a fixed seed for the RNG
  -V seconds    - fuzz for a maximum total time of seconds then terminate
  -E execs      - fuzz for a maximum number of total executions then terminate
  Note: -V/-E are not precise, they are checked after a queue entry is done
  which can be many minutes/execs later

Other stuff:
  -T text       - text banner to show on the screen
  -M / -S id    - distributed mode (see docs/parallel_fuzzing.md)
  -I command    - execute this command/script when a new crash is found
  -B bitmap.txt - mutate a specific test case, use the out/fuzz_bitmap file
  -C            - crash exploration mode (the peruvian rabbit thing)
  -e ext        - File extension for the temporarily generated test case

To view also the supported environment variables of afl-fuzz please use "-hh".

For additional help please consult /usr/local/share/doc/afl/README.md

    """)
    # Make sure these two are included
    parser.add_argument("-i", metavar="dir", dest="corpus_dir", default='/corpus',
                        help="input directory with test cases")
    parser.add_argument("-o", metavar="dir", dest="fuzz_out", default='/fuzz_out',
                        help="output directory for fuzzer findings")

    # Add our custom arguments
    parser.add_argument("-j", metavar="num instances", type=int, default=(get_nproc() // 2),
                        help="number of AFL instances to run (default = nproc / 2")
    parser.add_argument('--fuzz-dir', default='/*-fuzz',
                        help='absolute path to root of fuzz build')

    return parser


def append_afl_args(args, other_args):
    args.afl_args = ['-i', args.corpus_dir, '-o', args.fuzz_out, *other_args]


def validate_args(args):
    try:
        args.fuzz_dir = resolve_glob(args.fuzz_dir)
        args.fuzz_cmdline = resolve_cmdline_path(args.fuzz_dir, args.cmdline)
    except FileNotFoundError as e:
        die(e)

    # Handle incompatible/incomplete options
    if "-M" in args.afl_args or "-S" in args.afl_args:
        die("Please do not provide distributed mode options (-M, -S). We'll handle them")

    if "-n" in args.afl_args:
        die("Dumb fuzzing not supported in distributed mode. Use afl-fuzz")


if __name__ == "__main__":
    parser = init_parser()

    # Add args that conflict with afl-cov runner script
    parser.add_argument("-v", action="count", help="increase output verbosity")

    # I didn't want to have to add a switch for the target cmdline, but it was the
    # easiest way to distinguish between args for the target and generic args for AFL
    parser.add_argument('--exec', dest='cmdline', metavar='target_cmdline', nargs='*',
                        required=True, help='./relative_path/the_bin -a arg @@')

    # Any unknown arguments will be passed directly to afl-fuzz
    args, other_args = parser.parse_known_args()
    
    append_afl_args(args, other_args)
    validate_args(args)

    # Set root logger level (default = WARN, -v = INFO, -vv+ = DEBUG)
    if not args.v:
        level = logging.WARN
    elif args.v == 1:
        level = logging.INFO
    else:
        level = logging.DEBUG

    logging.getLogger().setLevel(level)

    # Start requested number of afl-fuzz instances
    for thread in start_afl_instances(args.j, args.afl_args, args.fuzz_cmdline):
        thread.join()
