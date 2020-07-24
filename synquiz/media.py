import re
import pickle
import subprocess
import logging

from pathlib import Path
from urllib import request, parse

import synquiz.util as util

log = logging.getLogger('synquiz')

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

def content_type(path):
    return content_types.get(Path(path).suffix, 'unknown/unknown')

def is_local_media(data):
    return not data['url'].lower().startswith('http')

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
    if data.get('type') == 'image':
        return data['url']
    if data.get('type') in ('audio', 'video'):
        return video_metadata(data)[1]
    return None

class Cache:
    def __init__(self, home):
        self.home = home
        self.db_file = self.home / 'db.pickle'
        self._prepare()

    def _prepare(self):
        if self.db_file.exists():
            self.cache = pickle.load(open(self.db_file, 'rb'))
        else:
            self.cache = {}

    def write(self):
        with open(self.db_file, 'wb') as f:
            pickle.dump(self.cache, f)

    def contains(self, key, data):
        if key in self.cache and (self.home / self.cache[key]).exists():
            log.debug('Media found in cache')
            data['file'] = self.cache[key]
            data['content_type'] = content_type(self.cache[key])
            return True
        return False

    def add(self, path, key, data):
        file = Path(path).relative_to(self.home)
        log.debug(f'Filename: {file}')

        data['file'] = file
        data['content_type'] = content_type(file)
        self.cache[key] = file

    def keys(self):
        return self.cache.keys()

    def remove(self, key):
        if key in self.cache:
            del self.cache[key]

    def __getitem__(self, key):
        return self.cache[key]

    def get(self, key):
        return self.cache.get(key)

class MediaManager:
    def __init__(self, home):
        self.home = home
        self.cache = Cache(self.home)

    def _handle_local_media(self, data):
        url = data['url']
        data['file'] = url
        data['content_type'] = content_type(url)

    def media_file(self, data):
        if 'url' not in data:
            return None
        if is_local_media(data):
            return self.home / data['url']
        key = media_cache_key(data)
        cached = self.cache.get(key)
        if cached:
            return self.home / cached
        return None

    def needs_downloading(self, data):
        if is_local_media(data):
            log.debug('Media determined to be local, no downloading necessary')
            self._handle_local_media(data)
            return False

        key = media_cache_key(data)
        if self.cache.contains(key, data):
            return False
        return True

    def handle_image(self, data):
        if not self.needs_downloading(data):
            return

        url = data['url']
        parsed = parse.urlparse(url)
        parts = parsed.path.split('.')
        if not parts:
            ext = 'img'
        ext = parts[-1].split('/')[0]

        dest = self.home / 'data' / f'{util.randstr()}.{ext}'

        log.info('Downloading media...')
        try:
            req = request.Request(url)
            req.add_header('User-Agent', 'Mozilla/5.0 (Windows; U; Windows NT 5.1; de; rv:1.9.1.5) Gecko/20091102 Firefox/3.5.5')
            resp = request.urlopen(req)
        except request.URLError:
            log.warning(f"Could not download image '{url}' for {data.get('title')}")
            return
        log.info('Image successfully downloaded')
        dest.write_bytes(resp.read())

        self.cache.add(dest, url, data)

    def handle_media(self, data):
        if not self.needs_downloading(data):
            return

        url = data['url']
        audio_only = data['type'] == 'audio'
        get_all, key = video_metadata(data)
        _, start, length = key
        name = util.randstr()
        file_format = f'{self.home}/data/{name}.%(ext)s'

        log.info('Downloading media...')

        extra_options = []
        if audio_only:
            extra_options = [
                '-x',
            ]

        postprocessor = []
        if not get_all:
            postprocessor = [
                '--postprocessor-args',
                f'-ss {util.to_hms(start)} -t {util.to_hms(length)}',
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
            log.warning(f"Error downloading '{url}' for {data.get('title')}")
            log.warning(result.stdout)
            return

        log.info('Media download done')

        file_re = re.compile(rf'\[(?:download|ffmpeg)\].*({self.home}/data/{name}\.[a-z0-9]+)')
        log.debug(result.stdout)
        match = file_re.findall(result.stdout)
        if not match:
            log.warning('No file name found for download {url}')
            log.warning(result.stdout)
            return
        full_path = match[-1]

        self.cache.add(full_path, key, data)


    def media_items(self, questions):
        res = []
        for q in questions:
            if util.is_media_type(q):
                res.append(q)
            if util.is_media_type(q.get('answer')):
                res.append(q['answer'])
            if q.get('type') == 'super':
                res.extend(self.media_items(q['questions']))
        return res

    def clean(self, quiz_data, remove_all=False):
        log.info('Cleaning up cached unused files')
        media = set(map(media_cache_key, self.media_items(quiz_data['quiz'])))
        keys = set(self.cache.keys())
        keys = keys - media

        if not keys:
            log.info('Nothing to do')
        else:
            log.info(f'{len(keys)} files to delete')
            for k in keys:
                path = self.home / self.cache[k]
                if path.is_file():
                    log.debug(f'Deleting {path}')
                    path.unlink()
                self.cache.remove(k)

            self.cache.write()

        if not remove_all:
            return

        log.info('Cleaning up all files not used in quiz')

        files = set(map(lambda x: self.media_file(x), self.media_items(quiz_data['quiz'])))
        data_files = set([p for p in (self.home / 'data').glob('*') if p.is_file()])
        to_delete = data_files - files

        if not to_delete:
            log.info('Nothing to do')
            return

        log.info(f'{len(to_delete)} files to delete')
        for p in to_delete:
            log.debug(f'Deleting {p}')
            p.unlink()

    def save_cache(self):
        self.cache.write()
