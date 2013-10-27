# coding=utf-8
"""Music file formats

Guessing of supported file formats and codecs based on extensions

"""

import os

from musa.config import MusaConfigDB
from musa.log import MusaLogger
from musa import normalized, MusaError, CommandPathCache
from musa.metadata import Metadata

logger = MusaLogger('formats').default_stream

TAG_PARSERS = {
    'm4a':      'musa.tags.formats.aac.aac',
    'mp3':      'musa.tags.formats.mp3.mp3',
    'flac':     'musa.tags.formats.flac.flac',
    'vorbis':   'musa.tags.formats.vorbis.vorbis',
}

PATH_CACHE = CommandPathCache()
PATH_CACHE.update()

db = MusaConfigDB()

def filter_available_command_list(commands):
    available = []
    for cmd in commands:
        try:
            executable = cmd.command.split(' ', 1)[0]
        except IndexError:
            executable = cmd.command
            pass
        if PATH_CACHE.which(executable) is None:
            continue
        available.append(cmd.command)
    return available

def match_codec(path):
    ext = os.path.splitext(path)[1][1:]

    if ext == '':
        ext = path

    if ext in db.codecs.keys():
        return db.codecs[ext]

    for codec in db.codecs.values():
        if ext in [e.extension for e in codec.extensions]:
            return codec

    return None

def match_metadata(path):
    metadata = Metadata()
    m = metadata.match(path)
    if m:
        return m
    return None

class path_string(unicode):
    def __init__(self, path):
        if isinstance(path, unicode):
            unicode.__init__(self, normalized(path).encode('utf-8'))
        else:
            unicode.__init__(self, normalized(path))

    @property
    def exists(self):
        if os.path.isdir(self) or os.path.isfile(self):
            return True
        return False

    @property
    def isdir(self):
        return os.path.isdir(self)

    @property
    def isfile(self):
        return os.path.isfile(self)

    @property
    def no_ext(self):
        return os.path.splitext(self)[0]

    @property
    def directory(self):
        return os.path.dirname(self)

    @property
    def filename(self):
        return os.path.basename(self)

    @property
    def extension(self):
        return os.path.splitext(self)[1][1:]

class MusaFileFormat(object):
    """MusaFileFormat

    Common file format wrapper for various codecs

    """

    def __init__(self, path):
        self.db = MusaConfigDB()
        self.log =  MusaLogger('formats').default_stream
        self.path = path_string(path)
        self.codec = None
        self.description = None
        self.is_metadata = False

        self.codec = match_codec(path)
        if self.codec is not None:
            self.description = self.codec.description.lower()
        else:
            m = match_metadata(path)
            if m:
                self.is_metadata = True
                self.description = m.description.lower()
            elif os.path.isdir(path):
                self.description = 'unknown directory'
            else:
                self.description = 'unknown file format'

    def __repr__(self):
        return '%s %s' % (self.codec, self.path)

    @property
    def directory(self):
        return os.path.dirname(self.path)

    @property
    def filename(self):
        return os.path.basename(self.path)

    @property
    def extension(self):
        return os.path.splitext(self.path)[1][1:]

    @property
    def size(self):
        if not self.path.isfile:
            return None
        return os.stat(self.path).st_size

    @property
    def ctime(self):
        if not self.path.isfile:
            return None
        return os.stat(self.path).st_ctime

    @property
    def mtime(self):
        if not self.path.isfile:
            return None
        return os.stat(self.path).st_mtime

    def get_tag_parser(self):
        if self.codec is None or self.codec.name not in TAG_PARSERS.keys():
            return None
        try:
            classpath = TAG_PARSERS[self.codec.name]
            module_path = '.'.join(classpath.split('.')[:-1])
            class_name = classpath.split('.')[-1]
            m = __import__(module_path, globals(), fromlist=[class_name])
            return getattr(m, class_name)
        except KeyError, emsg:
            #logger.debug('Error loading tag parser for %s' % self.path)
            return None

    def get_available_encoders(self):
        if self.codec is None or not self.codec.encoders:
            return []
        return filter_available_command_list(self.codec.encoders)

    def get_available_decoders(self):
        if self.codec is None or not self.codec.decoders:
            return []
        return filter_available_command_list(self.codec.decoders)

