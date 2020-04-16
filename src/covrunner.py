#!/usr/bin/env python3.7
import logging
import subprocess
import threading
import argparse
import sys
import socketserver
import os
from glob import glob
from time import sleep
from functools import partial
from utils import *

# TODO how to properly manage loggers without messing with the root logger?
logging.basicConfig(level=logging.WARNING, format="%(asctime)s | %(name)s | %(message)s",
                    datefmt='%Y-%d-%m %H:%M:%S')


def start_cov_and_serve(target_cmd: str, fuzz_out_dir: str, cov_dir: str, web_port: int):
    """
    Starts threads for afl-cov and python http.server
    :param target_cmd: Command-line to start the target program
    :param fuzz_out_dir: Absolute path of directory passed to afl-fuzz -o switch
    :param cov_dir: Absolute path to project root of the coverage build
    :param web_port: Port to serve the web report on
    :return: None
    """
    threads = list()

    # Start http.server
    srv_thread = threading.Thread(target=run_webserver, args=(fuzz_out_dir, web_port))
    srv_thread.start()
    threads.append(srv_thread)

    # Start afl-cov
    cov_thread = threading.Thread(target=run_afl_cov, args=(target_cmd, fuzz_out_dir, cov_dir))
    cov_thread.start()
    threads.append(cov_thread)

    # Once the afl-cov thread exits, we assume something has gone wrong or that the
    # user wants to exit
    for t in threads:
        t.join()


def run_afl_cov(target_cmdline: list, fuzz_out_dir: str, cov_dir: str):
    logger = logging.getLogger('AFL-COV')
    logger.warning(f"Starting afl-cov")

    # Create a cmdline string that contains the full path to the bin
    bin_path = os.path.realpath(os.path.join(cov_dir, target_cmdline[0]))
    tgt_cmd = f'{bin_path} {" ".join(target_cmdline[1:])}'
    if '@@' in tgt_cmd:
        # afl-cov uses "AFL_FILE" instead of "@@"
        tgt_cmd = tgt_cmd.replace('@@', 'AFL_FILE')
    else:
        # handle cases where the bin reads from stdin
        tgt_cmd = f'cat AFL_FILE | {tgt_cmd}'

    cov_args = ['/usr/bin/afl-cov', '-d', fuzz_out_dir, '--live', '--overwrite', '--lcov-web-all', '--coverage-cmd', tgt_cmd, '--code-dir', cov_dir]
    proc = subprocess.Popen(cov_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Quick check to see if we immediately died for some reason
    try:
        dead = True
        proc.wait(3.0)
    except subprocess.TimeoutExpired:
        dead = False
        pass
    finally:
        if dead:
            outs, errs = proc.communicate(timeout=1)
            if outs:
                die(outs.decode())
            if errs:
                die(errs.decode())

    # Parse afl-cov output so we can log each message in blocks instead of line by line
    block = []
    found_coverage = False
    logger.warning('Collecting code coverage')
    #import pdb; pdb.set_trace()
    for line in iter(proc.stdout.readline, b""):
        line = line.decode().strip()

        # Handle the various types of messages afl-cov logs
        if '[-]' in line:
            logger.debug(line.lstrip('[-] '))
        elif '[*]' in line:
            logger.warning(line.lstrip('[*] '))
        elif 'coverage' in line:
            if "'line'" in line:
                # Line coverage can be very verbose
                logger.debug(line)
            else:
                logger.info(line)
        else:
            logger.debug(line)

    # Check if anything went wrong
    proc.wait()
    if proc.returncode != 0:
        logger.critical("afl-cov returned non-zero exit code: %d" % proc.returncode)
        logger.critical("Failed command: " + ' '.join(proc.args))


def run_webserver(fuzz_out_dir, port):
    web_dir = f'{fuzz_out_dir}/cov/web'
    handler_class = partial(RequestHandler, directory=web_dir)
    socketserver.TCPServer.allow_reuse_address = True

    logger = logging.getLogger('WEB-SRV')
    logger.debug(f'Web directory is set to {web_dir}')
    logger.warning('Waiting for web report to be created...')

    # We need to hang out until the web report exists
    while not os.path.exists(f'{web_dir}/index.html'):
        sleep(1)

    with socketserver.TCPServer(('0.0.0.0', port), handler_class) as httpd:
        logger.warning('Web report created. Serving on port %d' % port)
        httpd.serve_forever()


def init_parser(add_help=True):
    parser = argparse.ArgumentParser(description='Run afl-cov and serve the web report', add_help=add_help)
    parser.add_argument('--cov-dir', default='/*-cov',
                        help='absolute path to the dir containing the coverage build')
    parser.add_argument('--port', type=int, default=8000,
                        help='port on which to serve the web report')
    parser.add_argument('--exec', dest='cmdline', metavar='target_cmdline', nargs='*',
                        required=True, help='./relative_path/the_bin -a arg @@')

    return parser


def validate_args(args):
    try: 
        args.cov_dir = resolve_glob(args.cov_dir)
        args.cov_cmdline = resolve_cmdline_path(args.cov_dir, args.cmdline)
    except FileNotFoundError as e:
        die(e)


if __name__ == "__main__":
    parser = init_parser()

    # Add args that conflict with afl-fuzz runner script
    parser.add_argument('-o', default='/fuzz_out',
                        help='absolute path to the fuzzer output directory')
    parser.add_argument("-v", action="count", help="increase output verbosity")
    args = parser.parse_args()

    validate_args(args)

    # Set root logger level (default = WARN, -v = INFO, -vv+ = DEBUG)
    if not args.v:
        level = logging.WARN
    elif args.v == 1:
        level = logging.INFO
    else:
        level = logging.DEBUG

    logging.getLogger().setLevel(level)

    # Start up afl-cov and serve the web report
    start_cov_and_serve(args.cov_cmdline, args.fuzz_out, args.cov_dir, args.port)
