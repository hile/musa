
import os,re

from musa.formats import MusaFileFormat,match_codec,match_metadata,CODECS
from musa.prefixes import TreePrefixes,PrefixError
from musa.tags import TagError
from musa.tags.tagparser import Tags

class TreeError(Exception):
    def __str__(self):
        return self.args[0]

class IterableTrackFolder(object):
    def __init__(self,path,iterable):
        self.__next = None
        self.__iterable = iterable
        self.path = path
        self.prefixes = TreePrefixes()
        self.invalid_paths = []
        self.has_been_iterated = False
        setattr(self,iterable,[])

    def __iter__(self):
        return self

    def __len__(self):
        iterable = getattr(self,self.__iterable)
        if len(iterable)==0:
            self.load()
        if len(iterable) - len(self.invalid_paths)>=0:
            return len(iterable) - len(self.invalid_paths)
        else:
            return 0

    def next(self):
        iterable = getattr(self,self.__iterable)
        if self.__next is None:
            self.__next = 0
            self.has_been_iterated = False
            if len(iterable)==0:
                self.load()
        try:
            entry = iterable[self.__next]
            self.__next += 1
            path = os.path.join(entry[0],entry[1])
            try:
                return Track(path)
            except TreeError:
                if not self.invalid_paths.count(path):
                    self.invalid_paths.append(path)
                return self.next()
        except IndexError:
            self.__next = None
            self.has_been_iterated = True
            raise StopIteration

    def load(self):
        iterable = getattr(self,self.__iterable)
        iterable.__delslice__(0,len(iterable))
        self.invalid_paths.__delslice__(0,len(self.invalid_paths))

    def relative_path(self,path):
        return self.prefixes.relative_path(path) 

class Tree(IterableTrackFolder):
    def __init__(self,path):
        IterableTrackFolder.__init__(self,path,'files')
        self.empty_dirs = []

    def __len__(self):
        """ 
        Tree must be loaded to figure out it's length
        """
        if not self.has_been_iterated:
            self.has_been_iterated = True
            while True:
                try:
                    self.next()
                except StopIteration:
                    break
        return IterableTrackFolder.__len__(self)

    def __cmp_file_path__(self,a,b):
        if a[0]!=b[0]:
            return cmp(a[0],b[0])
        return cmp(a[1],b[1])

    def load(self):
        if not os.path.isdir(self.path): 
            raise TreeError('Not a directory: %s' % self.path)

        IterableTrackFolder.load(self)
        self.empty_dirs.__delslice__(0,len(self.files))
        for (root,dirs,files) in os.walk(self.path,topdown=True):
            if files:
                self.files.extend((root,x) for x in files)
            elif not dirs:
                self.empty_dirs.append(root)
        self.files.sort(lambda x,y: self.__cmp_file_path__(x,y))

    def filter_tracks(self,regexp=None,re_path=True,re_file=True,as_tracks=False):
        if not len(self.files):
            self.load()
        tracks = filter(lambda f: match_codec(f[1]), self.files)
        if regexp is not None:
            if not re_file and not re_path:
                raise TreeError('No matches if both re_file and re_path are False')
            if isinstance(regexp,basestring):
                regexp = re.compile(regexp)
            tracks = filter(lambda t: 
                re_path and regexp.match(t[0]) or re_file and regexp.match(t[1]),
                tracks
            )
        if as_tracks:
            return [Track(os.path.join(t[0],t[1])) for t in tracks]
        else:
            return tracks

class Album(IterableTrackFolder):
    def __init__(self,path):
        IterableTrackFolder.__init__(self,path,'files')
        self.metadata = []

    def load(self):
        if not os.path.isdir(self.path): 
            raise TreeError('Not a directory: %s' % self.path)

        IterableTrackFolder.load(self)
        for f in os.listdir(self.path):
            if match_codec(f) is not None:  
                self.files.append((self.path,f))
            else:
                metadata = match_metadata(f)
                if metadata:
                    mdf = MetaDataFile(os.path.join(self.path,f),metadata) 
                    self.metadata.append(mdf)

class MetaDataFile(object):
    def __init__(self,path,metadata=None):
        if metadata is None:
            metadata = match_metadata(path)
            if metadata is None:
                raise TreeError('Not a metadata file: %s' % path)
        self.path = path
        self.extension = os.path.splitext(self.path)[1][1:].lower()
        if self.extension=='':
            self.extension = None
        self.metadata = metadata

    def __repr__(self):
        return self.extension is not None and self.extension or 'metadata'

class Track(MusaFileFormat):
    def __init__(self,path):
        MusaFileFormat.__init__(self,path)
        self.prefixes = TreePrefixes()
        if self.codec is None:
            raise TreeError('Not a music file: %s' % self.path)

        self.tags_loaded = False
        self.file_tags = None

    def __getattr__(self,attr):
        if attr=='tags':
            if not self.tags_loaded:
                self.tags_loaded = True
                try:
                    self.file_tags = Tags(self.path,fileformat=self)
                except TagError,emsg:
                    raise TreeError('Error loading tags: %s' % emsg)
            return self.file_tags
        raise AttributeError('No such Track attribute: %s' % attr)

    def relative_path(self):
        return self.prefixes.relative_path(self.path)

    def get_album_tracks(self):
        path = os.path.dirname(self.path)
        extensions = CODECS[self.codec]['extensions']
        tracks = []
        for t in os.listdir(path):
            if os.path.splitext(t)[1][1:] not in extensions:
                continue
            tracks.append(Track(os.path.join(path,t)))
        return tracks

    def get_encoder_command(self,wav_path=None):
        if wav_path is None:
            wav_path = '%s.wav' % os.path.splitext(self.path)[0]
        if wav_path == self.path:
            raise TreeError('Trying to encode to itself')
        try:
            encoder = self.get_available_encoders()[0]
        except IndexError:
            raise TreeError('No available encoders for %s' % self.path)
        encoder = encoder.replace('OUTFILE',self.path) 
        encoder = encoder.replace('FILE',wav_path) 
        return encoder

    def get_decoder_command(self,wav_path=None):
        if wav_path is None:
            wav_path = '%s.wav' % os.path.splitext(self.path)[0]
        if wav_path == self.path:
            raise TreeError('Trying to encode to itself')
        try:
            decoder = self.get_available_decoders()[0]
        except IndexError:
            raise TreeError('No available decoders for %s' % self.path)
        decoder = decoder.replace('OUTFILE',wav_path) 
        decoder = decoder.replace('FILE',self.path)
        return decoder

if __name__ == '__main__':
    import sys
    for f in sys.argv[1:]:
        try:
            tree = Tree(f)
            regexp = re.compile('.* perkele.*',re.IGNORECASE)
            regexp=None
            for track in tree:#tree.filter_tracks(regexp=regexp,as_tracks=False):
                print track.relative_path()
                #for tag,value in track.tags.items(): print '%s=%s' % (tag,value)
        except TreeError,emsg:
                print emsg

