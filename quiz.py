import yaml
import string
import pickle
import random
import subprocess
import os
import argparse
import time
import traceback
import shutil
import re
from urllib import request, parse
from pathlib import Path

from mako.template import Template
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

link_paths = [
    'data',
    'index.html',
]

content_types = {
    '.opus': 'audio/ogg',
    '.m4a': 'audio/mpeg',
    '.mp3': 'audio/mpeg',
    '.wav': 'audio/wav',

    '.mp4': 'video/mp4',
    '.mkv': 'video/mp4',
    '.gif': 'video/mp4',
    '.webm': 'video/webm',
    '.ogg': 'video/ogg',
}

HERE = Path(__file__).parent.resolve()

class Npm:
    def __enter__(self):
        os.chdir(reveal())
        self.process = subprocess.Popen(['npm', 'start'])
        return self

    def __exit__(self, type, value, traceback):
        if self.process and self.process.poll() is not None:
            print('Terminating npm')
            self.process.terminate()

def reveal():
    return args.dir / '..' / 'main'

def randstr():
    return ''.join([random.choice(string.ascii_lowercase) for _ in range(5)])

def to_hms(total):
    mins = int(total // 60)
    hours = int(mins // 60)
    secs = total % 60
    st = f'{hours:02}:{mins:02}:{secs:05.02f}'
    return st

def content_type(path):
    return content_types.get(Path(path).suffix, 'unknown/unknown')

def is_local_media(data):
    return not data['url'].startswith('http')

def handle_local_media(data):
    url = data['url']
    data['file'] = url
    data['content_type'] = content_type(url)

def media_in_cache(key, data, cache):
    if key in cache and (args.dir / cache[key]).exists():
        print('Media found in cache')
        data['file'] = cache[key]
        data['content_type'] = content_type(cache[key])
        return True
    return False

def add_to_cache(path, key, data, cache):
    file = Path(path).relative_to(args.dir)
    print(f'Filename: {file}')

    data['file'] = file
    data['content_type'] = content_type(file)
    cache[key] = file

def video_metadata(data):
    keys = ['start', 'end', 'len']

    # No length specified, whole media should be considered
    if not any(map(lambda x: x in data, keys)):
        return True, (data['url'], 0, 1000)

    start = data.get('start', 0)
    end = data.get('end', None)
    if end is None:
        length = data.get('len', 1000)
    else:
        assert end > start
        length = end - start

    return False, (data['url'], start, length)

def media_cache_key(data):
    if data['type'] == 'image':
        return data['url']
    if data['type'] in ('audio', 'video'):
        return video_metadata(data)[1]
    return None

def media_file(data, cache):
    if 'url' not in data:
        return None
    if is_local_media(data):
        return args.dir / data['url']
    key = media_cache_key(data)
    cached = cache.get(key)
    if cached:
        return args.dir / cached
    return None

def needs_downloading(data, cache):
    if is_local_media(data):
        print('Media determined to be local, no downloading necessary')
        handle_local_media(data)
        return False

    key = media_cache_key(data)
    if media_in_cache(key, data, cache):
        return False
    return True

def download_image(data, cache):
    if not needs_downloading(data, cache):
        return

    url = data['url']
    parsed = parse.urlparse(url)
    parts = parsed.path.split('.')
    if not parts:
        ext = 'img'
    ext = parts[-1].split('/')[0]

    dest = args.dir / 'data' / f'{randstr()}.{ext}'

    print('Downloading media...')
    try:
        resp = request.urlopen(url)
    except request.URLError:
        print('Could not download image')
        return
    print('Image successfully downloaded')
    dest.write_bytes(resp.read())

    add_to_cache(dest, url, data, cache)

def download_media(data, cache):
    if not needs_downloading(data, cache):
        return

    url = data['url']
    audio_only = data['type'] == 'audio'
    get_all, key = video_metadata(data)
    _, start, length = key
    name = randstr()
    file_format = f'{args.dir}/data/{name}.%(ext)s'

    print('Downloading media...')

    extra_options = []
    if audio_only:
        extra_options = [
            '-x',
        ]

    postprocessor = []
    if not get_all:
        postprocessor = [
            '--postprocessor-args', f'-ss {to_hms(start)} -t {to_hms(length)}',
        ]

    result = subprocess.run(
        [
            'youtube-dl',
            '-o',
            file_format,
            *postprocessor,
            *extra_options,
            url,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding='utf-8',
    )

    if result.returncode != 0:
        print(f'ERROR DOWNLOADING {url}')
        print(result.stdout)
        return

    print('Media download done')

    file_re = re.compile(rf'\[(?:download|ffmpeg)\].*({args.dir}/data/{name}\.[a-z0-9]+)')
    print(result.stdout)
    match = file_re.findall(result.stdout)
    if not match:
        print('No file name found for download {url}')
        print(result.stdout)
        return
    full_path = match[-1]

    add_to_cache(full_path, key, data, cache)

def is_media(data):
    return isinstance(data, dict) and data['type'] in ('audio', 'video', 'image')

def media_items(questions):
    res = []
    for q in questions:
        if is_media(q):
            res.append(q)
        if q['type'] == 'super':
            res.extend(media_items(q['questions']))
        if is_media(q.get('answer')):
            res.append(q['answer'])
    return res

class Quiz:
    def __init__(self, home):
        self.home = Path(home)
        self._prepare_cache()

        with open(home / 'quiz.yaml') as f:
            self.quiz_data = yaml.load(f)
            self.question_title = self.quiz_data.get('question_title', 'Question')


    def _prepare_cache(self):
        self.db_file = self.home / 'db.pickle'

        if self.db_file.exists():
            self.cache = pickle.load(open(self.db_file, 'rb'))
        else:
            self.cache = {}

    def _write_cache(self):
        with open(self.db_file, 'wb') as f:
            pickle.dump(self.cache, f)

    def parse(self):
        try:
            for i, question in enumerate(self.quiz_data['quiz']):
                self.handle(question, i)
            return self.quiz_data
        finally:
            self._write_cache()

    def clean(self, remove_all=False):
        print('Cleaning up cached unused files')
        media = set(map(media_cache_key,media_items(self.quiz_data['quiz'])))
        keys = set(self.cache.keys())
        keys = keys - media

        if not keys:
            print('Nothing to do')
            return

        print(f'{len(keys)} files to delete')
        for k in keys:
            path = self.home / self.cache[k]
            if path.is_file():
                print(f'Deleting {path}')
                path.unlink()
            del self.cache[k]

        self._write_cache()

        if not remove_all:
            return

        print('Cleaning up all files not used in quiz')

        files = set(map(lambda x: media_file(x, self.cache), media_items(self.quiz_data['quiz'])))
        data_files = set([p for p in (self.home / 'data').glob('*') if p.is_file()])
        to_delete = data_files - files

        if not to_delete:
            print('Nothing to do')
            return

        print(f'{len(to_delete)} files to delete')
        for p in to_delete:
            print(f'Deleting {p}')
            p.unlink()

    def handle_text(self, data):
        print('Type: text')

    def handle_audio(self, data):
        print('Type: audio')
        download_media(data, self.cache)

    def handle_video(self, data):
        print('Type: video')
        download_media(data, self.cache)

    def handle_image(self, data):
        print('Type: image')
        download_image(data, self.cache)

    def handle_super(self, data):
        print('Type: super')
        for i, question in enumerate(data['questions']):
            self.handle(question, data['number'], i)

    def handle(self, data, number, sub=None):
        if sub is None:
            sub = ''
        else:
            sub = f'{string.ascii_lowercase[sub]}'
        data['number'] = number
        title = f'{self.question_title} {number+1}{sub}'
        data['title'] = title
        print(f'Parsing: {title}')
        self.__getattribute__(f'handle_{data["type"]}')(data)

        answer = data.get('answer', '')
        if isinstance(answer, str):
            print('Simple text answer')
            return

        print('Media answer, handling media')
        self.__getattribute__(f'handle_{data["type"]}')(answer)



def setup_symlinks():
    for p in link_paths:
        (reveal() / p).symlink_to(args.dir / p)

def teardown_symlinks():
    for p in link_paths:
        (reveal() / p).unlink()

def render(both=False):
    try:
        quiz = Quiz(args.dir)
        quiz_data = quiz.parse()

        template = Template(filename=str(HERE / 'template.html'), output_encoding='utf-8')
        if not both:
            (args.dir / 'index.html').write_bytes(template.render(answers=args.answers, **quiz_data))
        else:
            (args.dir / 'index.html').write_bytes(template.render(answers=False, **quiz_data))
            (args.dir / 'answers.html').write_bytes(template.render(answers=True, **quiz_data))

    except:
        traceback.print_exc()

def watch():
    to_watch = args.dir / 'quiz.yaml'
    print(f"Watching '{to_watch}'")
    print(f"Press Ctrl+C to stop")
    to_watch_name = str(to_watch)
    render()

    class Handler(FileSystemEventHandler):
        def on_modified(self, event):
            if event.event_type == 'modified':
                if event.src_path == to_watch_name:
                    print('Change detected, building...')
                    render()
                    print('Done')

    observer = Observer()
    observer.schedule(Handler(), str(to_watch.parent))
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
    print('Watch stopped')

def generate(watch_file):
    with Npm() as npm:
        try:
            setup_symlinks()
            if not watch_file:
                render()
            else:
                watch()
            npm.process.wait()
        except KeyboardInterrupt:
            print('Quitting')
        finally:
            teardown_symlinks()

def cleanup(args):
    q = Quiz(args.dir)
    q.clean(args.aggressive)

def make(args):
    generate(False)

def watch_make(args):
    generate(True)

def finalize(args):
    copy_paths = ['css', 'js', 'lib']
    for p in copy_paths:
        dest = args.dir / p
        if dest.exists():
            print('Skipping', p)
        else:
            src = reveal() / p
            print(f'Copying {src} -> {dest}')
            shutil.copytree(src, dest)

    render(True)

def init(args):
    if args.dir.exists():
        print(f'Directory {args.dir} already exsits, exiting')
        return
    args.dir.mkdir()
    quizfile = args.dir / 'quiz.yaml'
    init_yaml = f'''title: {args.dir.name}
subtitle: Optional subtitle
quiz:
    - type: text
      text: A text question
      answer: An answer to a text question

    - type: image
      text: An image question
      url: http://example.com
      answer: The answer to the image question

    - type: video
      text: A video question
      url: http://example.com
      answer: The answer to the video question

    - type: audio
      text: An audio question
      url: http://example.com
      start: 39.5
      len: 61
      answer: The answer to the audio question
'''
    quizfile.write_text(init_yaml)
    print(f'Quiz initialized in {quizfile}')

def _dir_type(st):
    return Path(st).resolve()

parser = argparse.ArgumentParser(description='Create quizzes from YAML files.')
parser.set_defaults(func=lambda _: parser.print_help())
subparsers = parser.add_subparsers()

parser_init = subparsers.add_parser('init', help='Initialize a quiz directory')
parser_init.set_defaults(func=init)

parser_make = subparsers.add_parser('make', help='Build a PDF lecture from a markdown file.')
parser_make.set_defaults(func=make)

parser_watch = subparsers.add_parser('watch', help='Monitor a quiz and build slides when it changes.')
parser_watch.set_defaults(func=watch_make)

parser_finalize = subparsers.add_parser('finalize', help='Finalize and make a standalone quiz')
parser_finalize.set_defaults(func=finalize)

parser_cleanup = subparsers.add_parser('clean', help='Remove unused media files')
parser_cleanup.add_argument('--aggressive', '-a', action='store_true', help='Remove all files from data directory, not just the ones downloaded by quiz')
parser_cleanup.set_defaults(func=cleanup)

parsers = [parser_watch, parser_make, parser_finalize, parser_cleanup, parser_init]

for p in parsers:
    p.add_argument('dir', help='Quiz directory', type=_dir_type)

for p in parsers[:2]:
    p.add_argument('--answers', '-a', action='store_true', help='Show answers')

args = parser.parse_args()



args.func(args)
