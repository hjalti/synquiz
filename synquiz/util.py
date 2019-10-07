import random
import string
import subprocess
import os
import logging

from pathlib import Path

log = logging.getLogger('synquiz')

DATA_DIR = Path(__file__).resolve().parent.parent / 'data'
TEMPLATE_FILE = DATA_DIR / 'template.html'

def randstr():
    return ''.join([random.choice(string.ascii_lowercase) for _ in range(5)])

def check_data_dir(home):
    (home / 'data').mkdir(exist_ok=True)

def is_media_type(data):
    return isinstance(data, dict) and data['type'] in ('audio', 'video', 'image')

def to_hms(total):
    mins = int(total // 60)
    hours = int(mins // 60)
    secs = total % 60
    st = f'{hours:02}:{mins:02}:{secs:05.02f}'
    return st

class NpmRunner:
    def __init__(self, reveal_dir):
        self.reveal_dir = reveal_dir

    def __enter__(self):
        os.chdir(self.reveal_dir)
        self.process = subprocess.Popen(['npm', 'start'])
        return self

    def __exit__(self, type, value, traceback):
        if self.process and self.process.poll() is not None:
            log.info('Terminating npm')
            self.process.terminate()

