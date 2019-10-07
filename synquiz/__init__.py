import argparse
from pathlib import Path

import synquiz.manage as manage
from .synquiz import init, make, watch_make, finalize, cleanup
from .output import setup_logger
from .util import TEMPLATE_FILE

def _dir_type(st):
    return Path(st).resolve()

parser = argparse.ArgumentParser(description='Create quizzes from YAML files.')
parser.set_defaults(func=lambda _: parser.print_help())
parser.add_argument('--quiet', '-q', action='count', help='Less output', default=0)
parser.add_argument('--reveal-dir', help='Reveal directory (default: %(default)s)', default=Path.home() / '.synquiz')
parser.add_argument('--template-file', help='Template file to use (default: %(default)s)', default=TEMPLATE_FILE)
subparsers = parser.add_subparsers()

parser_init = subparsers.add_parser('init', help='Initialize a quiz directory')
parser_init.set_defaults(func=init)

parser_make = subparsers.add_parser('make', help='Build a PDF lecture from a markdown file.')
parser_make.set_defaults(func=make)

parser_watch = subparsers.add_parser('watch', help='Monitor a quiz and build slides when it changes.')
parser_watch.set_defaults(func=watch_make)
parser_watch.add_argument('--development', '-d', action='store_true', help='Set develpment mode. Show both answerless version and asnwer version.')

parser_finalize = subparsers.add_parser('finalize', help='Finalize and make a standalone quiz')
parser_finalize.set_defaults(func=finalize)

parser_cleanup = subparsers.add_parser('clean', help='Remove unused media files')
parser_cleanup.add_argument('--aggressive', '-a', action='store_true', help='Remove all files from data directory, not just the ones downloaded by quiz')
parser_cleanup.set_defaults(func=cleanup)

# MANAGEMENT PARSERS

parser_manage = subparsers.add_parser('manage', help='Quiz management')
parser_manage.set_defaults(func=lambda _: parser_manage.print_help())
manage_subparsers = parser_manage.add_subparsers()

manage_cache = manage_subparsers.add_parser('cache', help='Show contents of quiz cache')
manage_cache.set_defaults(func=manage.show_db)

manage_init = manage_subparsers.add_parser('init', help='Initialize Synquiz on this machine')
manage_init.set_defaults(func=manage.init)

manage_clean = manage_subparsers.add_parser('clean', help='Remove Reveal.js directory')
manage_clean.set_defaults(func=manage.clean)

manage_template = manage_subparsers.add_parser('template', help='Get default quiz template')
manage_template.set_defaults(func=manage.template)

parsers = [parser_watch, parser_make, parser_finalize, parser_cleanup, parser_init, manage_cache]

for p in parsers:
    p.add_argument('dir', help='Quiz directory', type=_dir_type)
    p.set_defaults(development=False)

for p in parsers[:2]:
    p.add_argument('--answers', '-a', action='store_true', help='Show answers')

def main():
    args = parser.parse_args()
    setup_logger(10 + args.quiet*10)
    manage.check_dependencies()
    args.func(args)
