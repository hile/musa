"""
Tree prefixes configuration
"""

import os,configobj
from musa import MUSA_USER_DIR
from musa.log import MusaLogger
from musa.formats import match_codec,path_string,CODECS

USER_PATH_CONFIG = os.path.join(MUSA_USER_DIR,'paths.conf')

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

    @property
    def realpath(self):
        return os.path.realpath(self.path)

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
            return path_string(path[len(self.path):].lstrip(os.sep))
        realpath = os.path.realpath(path)
        if realpath[:len(self.path)] == self.path:
            return  path_string(realpath[len(self.path):].lstrip(os.sep))
        raise PrefixError('Prefix does not match: %s' % path)

class TreePrefixes(list):
    __instance = None

    def __init__(self):
        if not TreePrefixes.__instance:
            TreePrefixes.__instance = TreePrefixes.TreePrefixInstance()
            self.__dict__['TreePrefixes.__instance'] = TreePrefixes.__instance


    class TreePrefixInstance(list):
        def __init__(self):
            list.__init__(self)
            self.log = MusaLogger('musa').default_stream
            for path in DEFAULT_PATHS:
                for codec,defaults in CODECS.items():
                    prefix_path=os.path.join(path,codec)
                    prefix = MusicTreePrefix(prefix_path,defaults['extensions'])
                    self.register_prefix(prefix)

                if 'aac' in CODECS.keys():
                    prefix_path=os.path.join(path,'m4a')
                    prefix = MusicTreePrefix(prefix_path,CODECS['aac']['extensions'])
                    self.register_prefix(prefix)

            itunes_prefix = MusicTreePrefix(ITUNES_MUSIC,CODECS['aac']['extensions'])
            self.register_prefix(itunes_prefix)
            self.sort(lambda x,y: cmp(x.path,y.path))
            self.load_user_config()

        def load_user_config(self):
            if not os.path.isfile(USER_PATH_CONFIG):
                return

            with open(USER_PATH_CONFIG,'r') as config:

                user_codecs = {}
                for line in config:
                    try:
                        if line.strip()=='' or line[:1]=='#':
                            continue
                        (codec_name,paths) = [x.strip() for x in line.split('=',1)]
                        paths = [x.strip() for x in paths.split(',')]
                    except ValueError:
                        self.log.debug('Error parsing line: %s' % line)
                        continue
                    user_codecs[codec_name] = paths

                for codec_name in reversed(sorted(user_codecs.keys())):
                    paths = user_codecs[codec_name]
                    if codec_name=='itunes':
                        codec = match_codec('m4a')
                    else:
                        codec = match_codec(codec_name)
                    if not codec:
                        continue

                    for path in reversed(paths):
                        prefix = MusicTreePrefix(path,CODECS[codec]['extensions'])
                        if codec_name=='itunes':
                            self.register_prefix(prefix,prepend=False)
                        else:
                            self.register_prefix(prefix,prepend=True)

        def index(self,prefix):
            if not isinstance(prefix,MusicTreePrefix):
                raise PrefixError('Prefix must be MusicTreePrefix instance')
            for index,existing in enumerate(self):
                if prefix.realpath == existing.realpath:
                    return index
            raise IndexError('Prefix is not registered')

        def register_prefix(self,prefix,extensions=[],prepend=False):
            if isinstance(prefix,basestring):
                prefix = MusicTreePrefix(prefix,extensions)
            if not isinstance(prefix,MusicTreePrefix):
                raise PrefixError('prefix must be string or MusicTreePrefix instance')
            try:
                index = self.index(prefix)
                if prepend and index!=0:
                    prefix = self.pop(index)
                    self.insert(0,prefix)
            except IndexError:
                if prepend:
                    self.insert(0,prefix)
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
                    continue
                if prefix.match(path):
                    return prefix
            return None

        def relative_path(self,path):
            prefix = self.match(path)
            if not prefix:
                return path
            return prefix.relative_path(path)

    def __getattr__(self,attr):
        return getattr(self.__instance,attr)

    def __setattr__(self,attr,value):
        return setattr(self.__instance,attr,value)
