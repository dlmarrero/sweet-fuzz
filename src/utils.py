import sys
import os
from glob import glob
from http.server import SimpleHTTPRequestHandler


class RequestHandler(SimpleHTTPRequestHandler):
    '''
    The only purpose of creating this is to override log_message
    '''
    def __init__(self, *args, directory=None, **kwargs):
        super().__init__(*args, directory=directory, **kwargs)

    def log_message(self, format, *args):
        # We don't wanna log things from http.server
        return


def die(msg, code = 1):
    print(msg, file=sys.stderr)
    exit(code)


def resolve_glob(glob_path):
    # Need to glob in $SRC_DIR/../ since the location of SRC_DIR 
    # is arbitrary and the other build dirs will always be siblings
    src_dir = os.getenv('SRC_DIR')
    if not src_dir:
        die('SRC_DIR enviornment variable not set!')

    parent_dir = f'{src_dir}/../'
    search_path = os.path.abspath(os.path.join(parent_dir, glob_path))

    paths = glob(search_path)

    # Make sure we got exactly one result
    if len(paths) is 0:
        die(f'Glob search for source dir failed ({search_path})')
    if len(paths) > 1:
        die('Glob search returned multiple results: ' + str(paths))

    return paths[0]


def resolve_cmdline_path(root_dir: str, cmdline: list):
    if not os.path.exists(root_dir):
        raise FileNotFoundError(f'Directory {root_dir} does not exist!')
    
    new_cmdline = list(cmdline)
    if not os.path.isabs(new_cmdline[0]):
        new_cmdline[0] = os.path.realpath(os.path.join(root_dir, new_cmdline[0]))
    else:
        raise FileNotFoundError('--exec path to binary must be relative from project root')

    if not os.path.exists(new_cmdline[0]):
        raise FileNotFoundError(f'Could not find binary at {new_cmdline[0]}!\n' +
            f'--exec arg must be relative to {root_dir}')

    return new_cmdline
