# coding=utf-8
"""Tree prefixes

Tree prefixes configuration

"""

import os
import configobj

from musa.defaults import MUSA_USER_DIR
from musa.config import MusaConfigDB
from musa.log import MusaLogger
from musa.formats import match_codec, path_string

USER_PATH_CONFIG = os.path.join(MUSA_USER_DIR, 'paths.conf')

DEFAULT_PATHS = [
    '/music',
    '/Volumes/Media',
    os.path.join(os.getenv('HOME'), 'Music')
]

ITUNES_MUSIC = os.path.join(
    os.getenv('HOME'), 'Music', 'iTunes', 'iTunes Media', 'Music'
)
ITUNES_PARTS = ITUNES_MUSIC.split(os.sep)
for i in range(0, len(ITUNES_PARTS)+1):
    if os.path.islink(os.sep.join(ITUNES_PARTS[:i])):
        ITUNES_MUSIC = os.path.realpath(ITUNES_MUSIC)
        break


class PrefixError(Exception):

    def __str__(self):
        return self.args[0]


class MusicTreePrefix(object):

    """MusicTreePrefix

    Tree path prefix matcher

    """
    def __init__(self,path,extensions=[]):
        self.log = MusaLogger('musa').default_stream
        self.path = path.rstrip(os.sep)
        if not isinstance(extensions, list):
            raise PrefixError('Extensions must be a list')

        self.extensions = []
        for ext in extensions:
            if hasattr(ext, 'extension'):
                ext = ext.extension
            elif not isinstance(ext, basestring):
                raise PrefixError('Extensions must be a list of strings')

            if not isinstance(ext,unicode):
                ext = unicode(ext,'utf-8')

            if self.extensions.count(ext)==0:
                self.extensions.append(ext)

    def __repr__(self):
        if self.extensions:
            return '%s (%s)' % (self.path, ','.join(self.extensions))
        else:
            return self.path

    @property
    def realpath(self):
        return os.path.realpath(self.path)

    def match(self, path):
        if path[:len(self.path)] == self.path:
            return True

        realpath = os.path.realpath(path)
        mypath = os.path.realpath(self.path)
        if realpath[:len(mypath)] == mypath:
            return True

        return False

    def match_extension(self, extension):
        if not isinstance(extension,unicode):
            extension = unicode(extension,'utf-8')
        return extension in self.extensions

    def relative_path(self, path):
        path = path.rstrip(os.sep)
        if path[:len(self.path)] == self.path:
            return path_string(path[len(self.path):].lstrip(os.sep))

        realpath = os.path.realpath(path)
        mypath = os.path.realpath(self.path)

        if realpath[:len(mypath)] == mypath:
            return path_string(realpath[len(mypath):].lstrip(os.sep))

        raise PrefixError('Prefix does not match: %s' % path)


class TreePrefixes(object):

    """TreePrefixes

    List of known or common music tree prefixes

    """
    __instance = None

    def __init__(self):
        if TreePrefixes.__instance is None:
            TreePrefixes.__instance = TreePrefixes.TreePrefixInstance()
            self.__dict__['TreePrefixes.__instance'] = TreePrefixes.__instance

    class TreePrefixInstance(list):

        def __init__(self):
            self.log = MusaLogger('musa').default_stream
            list.__init__(self)
            self.db = MusaConfigDB()

            for path in DEFAULT_PATHS:
                for name,codec in self.db.codecs.items():
                    prefix_path = os.path.join(path, name)
                    prefix = MusicTreePrefix(prefix_path, [codec.name] + codec.extensions)
                    self.register_prefix(prefix)

                if 'm4a' in self.db.codecs.keys():
                    prefix_path = os.path.join(path, 'm4a')
                    prefix = MusicTreePrefix(prefix_path, self.db.codecs.extensions('m4a'))
                    self.register_prefix(prefix)

            itunes_prefix = MusicTreePrefix(ITUNES_MUSIC, self.db.codecs.extensions('m4a'))
            self.register_prefix(itunes_prefix)
            #self.sort(lambda x, y: cmp(x.path, y.path))
            self.load_user_config()

        def load_user_config(self):
            if not os.path.isfile(USER_PATH_CONFIG):
                return

            with open(USER_PATH_CONFIG, 'r') as config:

                user_codecs = {}
                for line in config:
                    try:
                        if line.strip() == '' or line[:1] == '#':
                            continue
                        (codec_name, paths) = [x.strip() for x in line.split('=', 1)]
                        paths = [x.strip() for x in paths.split(',')]
                    except ValueError:
                        self.log.debug('Error parsing line: %s' % line)
                        continue
                    user_codecs[codec_name] = paths

                for codec_name in reversed(sorted(user_codecs.keys())):
                    paths = user_codecs[codec_name]
                    if codec_name == 'itunes':
                        codec = match_codec('m4a')
                    else:
                        codec = match_codec(codec_name)
                    if not codec:
                        continue

                    for path in reversed(paths):
                        prefix = MusicTreePrefix(path, self.db.codecs.extensions('aac'))
                        if codec_name == 'itunes':
                            self.register_prefix(prefix, prepend=False)
                        else:
                            self.register_prefix(prefix, prepend=True)

        def index(self, prefix):
            if not isinstance(prefix, MusicTreePrefix):
                raise PrefixError('Prefix must be MusicTreePrefix instance')

            for index, existing in enumerate(self):
                if prefix.realpath == existing.realpath:
                    return index

            raise IndexError('Prefix is not registered')

        def register_prefix(self,prefix,extensions=[],prepend=False):
            if isinstance(prefix, basestring):
                prefix = MusicTreePrefix(prefix, extensions)

            if not isinstance(prefix, MusicTreePrefix):
                raise PrefixError('prefix must be string or MusicTreePrefix instance')

            try:
                index = self.index(prefix)
                if prepend and index != 0:
                    prefix = self.pop(index)
                    self.insert(0, prefix)
            except IndexError:
                if prepend:
                    self.insert(0, prefix)
                else:
                    self.append(prefix)

        def match_extension(self,extension,match_existing=False):
            for prefix in self:
                if match_existing and not os.path.isdir(prefix.path):
                    continue

                if prefix.match_extension(extension):
                    return prefix

            return None

        def match(self,path,match_existing=False):
            for prefix in self:

                if match_existing and not os.path.isdir(prefix.path):
                    self.log.debug('skip unavailable prefix: %s' % prefix.path)
                    continue

                if prefix.match(path):
                    return prefix

            self.log.debug('no match for %s' % path)
            return None

        def relative_path(self, path):
            prefix = self.match(path)
            if not prefix:
                return path

            return prefix.relative_path(path)

    def __getattr__(self, attr):
        return getattr(self.__instance, attr)

    def __setattr__(self, attr, value):
        return setattr(self.__instance, attr, value)

