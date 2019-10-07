import os
import logging
import subprocess
import shutil

from .media import Cache
from .util import TEMPLATE_FILE

log = logging.getLogger('synquiz')

DEPENDENCIES = ['npm', 'git']

def check_dependencies():
    for d in DEPENDENCIES:
        if not shutil.which(d):
            log.error(f"Missing dependency '{d}', Synquiz will not work as expected")

def patch_node_12(target):
    res = subprocess.run(['node', '-v'], capture_output=True, universal_newlines=True)
    is_v12 = res.stdout.startswith('v12')
    if not is_v12:
        return

    log.info('Applying patch to Reveal.js for Node 12')
    p_json = target / 'package.json'
    package = p_json.read_text()
    p_json.write_text(package.replace('"node-sass": "^4.11.0",', '"node-sass": "^4.12.0",'))


def init(args):
    target = args.reveal_dir
    if target.is_dir():
        log.info(f'Synquiz already initialized')
        return
    elif target.exists():
        log.error(f"'{target}' already exists but is not a directory, aborting")
        return

    log.info(f'Cloning Reveal.js from github into {target}')
    subprocess.run(['git', 'clone', 'https://github.com/hakimel/reveal.js.git', str(target)])
    patch_node_12(target)

    os.chdir(target)
    log.info(f'Running npm install in Reveal.js')
    subprocess.run(['npm', 'install'])
    (target / 'index.html').unlink()

def clean(args):
    target = args.reveal_dir
    log.info(f'Removing Reveal.js directory {target}')
    if not target.is_dir():
        log.warning(f"'{target}' is not a directory, ignoring")
        return
    shutil.rmtree(target)

def show_db(args):
    log.info(f'Contents of cache for {args.dir}')
    c = Cache(args.dir)
    for k,v in c.cache.items():
        log.info(f'  {k} -> {v}')

def template(args):
    print(TEMPLATE_FILE.read_text())
