"""
Tree prefixes configuration
"""

import os
from musa.formats import CODECS

DEFAULT_PATHS = [
    '/music',
    '/Volumes/Media',
    os.path.join(os.getenv('HOME'),'Music')
]

ITUNES_MUSIC = os.path.join(
    os.getenv('HOME'),'Music','iTunes','iTunes Media','Music'
)
ITUNES_PARTS = ITUNES_MUSIC.split(os.sep)
for i in range(0,len(ITUNES_PARTS)+1):
    if os.path.islink(os.sep.join(ITUNES_PARTS[:i])):
        ITUNES_MUSIC = os.path.realpath(ITUNES_MUSIC)
        break

class PrefixError(Exception):
    def __str__(self):
        return self.args[0]

class MusicTreePrefix(object):
    def __init__(self,path,extensions=[]):
        self.path = path.rstrip(os.sep)
        if not isinstance(extensions,list):
            raise PrefixError('Extensions must be a list')
        for ext in extensions:
            if not isinstance(ext,basestring):
                raise PrefixError('Extensions must be a list of strings')
        self.extensions = extensions

    def __repr__(self):
        if self.extensions:
            return '%s (%s)' % (self.path,','.join(self.extensions))
        else:
            return self.path

    def match(self,path):
        path = path.rstrip(os.sep)
        if path[:len(self.path)] == self.path:
            return True
        realpath = os.path.realpath(path)
        if realpath[:len(self.path)] == self.path:
            return True
        return False

    def match_extension(self,extension):
        return extension in self.extensions

    def relative_path(self,path):
        path = path.rstrip(os.sep)
        if path[:len(self.path)] == self.path:
            return path[len(self.path):].lstrip(os.sep)
        realpath = os.path.realpath(path)
        if realpath[:len(self.path)] == self.path:
            return  realpath[len(self.path):].lstrip(os.sep)
        raise PrefixError('Prefix does not match: %s' % path)

class TreePrefixes(list):
    __instance = None

    class TreePrefixInstance(list):
        def __init__(self):
            list.__init__(self)
            for path in DEFAULT_PATHS:
                for codec,defaults in CODECS.items():
                    prefix_path=os.path.join(path,codec)
                    self.append(MusicTreePrefix(prefix_path,defaults['extensions']))

            if 'aac' in CODECS.keys():
                prefix_path=os.path.join(path,'m4a')
                self.append(MusicTreePrefix(
                    prefix_path,
                    CODECS['aac']['extensions']
                ))

            self.append(MusicTreePrefix(ITUNES_MUSIC,CODECS['aac']['extensions']))
            self.sort(lambda x,y: cmp(x.path,y.path))

    def __init__(self):
        if not TreePrefixes.__instance:
            TreePrefixes.__instance = TreePrefixes.TreePrefixInstance()
            self.__dict__['TreePrefixes.__instance'] = TreePrefixes.__instance

    def register_prefix(self,prefix,extensions=[]):
        if isinstance(prefix,MusicTreePrefix):
            self.__instance.append(prefix)
        elif isinstance(prefix,basestring):
            self.__instance.append(MusicTreePrefix(prefix,extensions))
        else:
            raise PrefixError('prefix must be string or MusicTreePrefix instance')

    def match(self,path):
        for prefix in self.__instance:
            if prefix.match(path):
                return prefix
        return None

    def relative_path(self,path):
        prefix = self.match(path)
        if not prefix:
            return path
        return prefix.relative_path(path)

