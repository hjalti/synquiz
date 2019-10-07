import yaml
import string
import time
import shutil
import logging

from mako.template import Template
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

import synquiz.util as util
import synquiz.validator as validator
from .media import MediaManager

log = logging.getLogger('synquiz')

link_paths = [
    'data',
    'index.html',
]

TYPES = ['text', 'audio', 'video', 'image', 'super']

class Quiz:
    def __init__(self, home):
        self.home = home
        self.media_manager = MediaManager(self.home)

        with open(home / 'quiz.yaml') as f:
            self.quiz_data = yaml.load(f, Loader=yaml.SafeLoader)
            self.question_title = self.quiz_data.get('question_title', 'Question')

    def parse(self):
        log.debug(f'Parsing Quiz metadata')
        try:
            validator.required(self.quiz_data, ['title', 'subtitle'])
            for i, question in enumerate(self.quiz_data['quiz']):
                self.handle(question, i)
            return self.quiz_data
        except validator.ValidationFailed as ex:
            log.error(f'Validation failed for {ex.identity()}')
            log.error('  ' + ex.message)
            raise
        finally:
            self.media_manager.save_cache()

    def handle_text(self, data):
        log.debug('Type: text')

    def handle_media(self, data):
        log.debug(f'Type: {data["type"]}')
        validator.required(data, ['url'])
        validator.mutually_exclusive(data, ['end', 'len'])
        self.media_manager.handle_media(data)

    handle_audio = handle_media
    handle_video = handle_media

    def handle_image(self, data):
        validator.required(data, ['url'])
        log.debug('Type: image')
        self.media_manager.handle_image(data)

    def handle_super(self, data):
        log.debug('Type: super')
        validator.non_empty(data, 'questions')

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
        log.debug(f'Parsing: {title}')
        data.setdefault('type', 'text')

        validator.one_of(data, 'type', TYPES)

        getattr(self, f'handle_{data["type"]}')(data)

        answer = data.get('answer', '')
        if not util.is_media_type(answer):
            log.debug('Simple text answer')
            return

        log.debug('Media answer, handling media')
        # For debugging purposes
        answer['title'] = f'Answer to {title}'
        getattr(self, f'handle_{answer["type"]}')(answer)

    def clean_media(self, remove_all):
        self.media_manager.clean(self.quiz_data, remove_all)

def setup_symlinks(args):
    for p in link_paths:
        (args.reveal_dir / p).symlink_to(args.dir / p)

def teardown_symlinks(args):
    for p in link_paths:
        (args.reveal_dir / p).unlink()

def render(args, both=False):
    try:
        quiz = Quiz(args.dir)
        quiz_data = quiz.parse()

        template = Template(filename=str(args.template_file), output_encoding='utf-8')
        if not both:
            development = bool(getattr(args, 'development'))
            (args.dir / 'index.html').write_bytes(template.render(answers=args.answers, development=development, **quiz_data))
        else:
            (args.dir / 'index.html').write_bytes(template.render(answers=False, **quiz_data))
            (args.dir / 'answers.html').write_bytes(template.render(answers=True, **quiz_data))

    except validator.ValidationFailed:
        pass
    except:
        log.exception('Something went wrong')

def watch(args):
    to_watch = args.dir / 'quiz.yaml'
    log.info(f"Watching '{to_watch}'")
    log.info(f"Press Ctrl+C to stop")
    to_watch_name = str(to_watch)
    render(args)

    class Handler(FileSystemEventHandler):
        def on_modified(self, event):
            if event.event_type == 'modified':
                if event.src_path == to_watch_name:
                    log.info('Change detected, building...')
                    render(args)
                    log.info('Done')

    observer = Observer()
    observer.schedule(Handler(), str(to_watch.parent))
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
    log.info('Watch stopped')

def generate(args, watch_file):
    util.check_data_dir(args.dir)
    with util.NpmRunner(args.reveal_dir) as npm:
        try:
            setup_symlinks(args)
            if not watch_file:
                render(args)
            else:
                watch(args)
            npm.process.wait()
        except KeyboardInterrupt:
            log.info('Quitting')
        finally:
            teardown_symlinks(args)

def cleanup(args):
    q = Quiz(args.dir)
    q.clean_media(args.aggressive)

def make(args):
    generate(args, False)

def watch_make(args):
    generate(args, True)

def finalize(args):
    util.check_data_dir(args.dir)
    copy_paths = ['css', 'js', 'lib']
    log.info('Copying required files')
    for p in copy_paths:
        dest = args.dir / p
        if dest.exists():
            log.info(f'  Skipping {p}')
        else:
            src = args.reveal_dir / p
            log.info(f'  Copying {src} -> {dest}')
            shutil.copytree(src, dest)

    render(args, True)
    log.info('Quiz successfully finalized')

def init(args):
    if args.dir.exists():
        log.info(f'Directory {args.dir} already exsits, exiting')
        return
    args.dir.mkdir()
    quizfile = args.dir / 'quiz.yaml'
    util.check_data_dir(args.dir)
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
    log.info(f'Quiz initialized in {quizfile}')
