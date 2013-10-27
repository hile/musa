# coding=utf-8
"""Tree, album  and track

Abstraction of filesystem audio file trees, albums and tracks

"""

import os
import re
import shutil
import time

from musa import normalized
from musa.log import MusaLogger
from musa.config import MusaConfigDB
from musa.formats import MusaFileFormat, path_string, match_codec, match_metadata
from musa.prefixes import TreePrefixes, PrefixError
from musa.tags import TagError
from musa.tags.albumart import AlbumArt, AlbumArtError
from musa.metadata import CoverArt
from musa.tags.tagparser import Tags


class TreeError(Exception):

    def __str__(self):
        return self.args[0]


class IterableTrackFolder(object):
    """IterableTrackFolder model

    Abstract class for various iterable music items

    """

    def __init__(self, path, iterable):
        self.config = MusaConfigDB()
        self.log = MusaLogger('musa').default_stream
        self.__next = None
        self.__iterable = iterable
        if path in ['.', '']:
            path = os.path.realpath(path)
        self.path = path_string(path)
        self.prefixes = TreePrefixes()
        self.invalid_paths = []
        self.has_been_iterated = False
        setattr(self, iterable, [])

    def __getitem__(self, item):
        if not self.has_been_iterated:
            self.load()
        iterable = getattr(self, self.__iterable)
        return iterable[item]

    def __len__(self):
        iterable = getattr(self, self.__iterable)
        if len(iterable) == 0:
            self.load()
        if len(iterable) - len(self.invalid_paths) >= 0:
            return len(iterable) - len(self.invalid_paths)
        else:
            return 0

    def __iter__(self):
        return self

    def next(self):
        iterable = getattr(self, self.__iterable)
        if self.__next is None:
            self.__next = 0
            self.has_been_iterated = False
            if len(iterable) == 0:
                self.load()
        try:
            entry = iterable[self.__next]
            self.__next += 1
            path = os.path.join(entry[0], entry[1])
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
        """Lazy loader of the iterable item"""
        iterable = getattr(self, self.__iterable)
        iterable.__delslice__(0, len(iterable))
        self.invalid_paths.__delslice__(0, len(self.invalid_paths))

    def relative_path(self, item=None):
        """Returns relative path of this iterable item"""

        if item is not None:
            if isinstance(item, Track):
                return self.prefixes.relative_path(item.path)
            else:
                return self.prefixes.relative_path(item)

        else:
            return self.prefixes.relative_path(self.path)

    def remove_empty_path(self, empty):
        """
        Remove empty directory and all empty parent directories
        """
        while True:
            if not os.path.isdir(empty):
                # Directory does not exist
                return
            if os.listdir(empty):
                # Directory is not empty
                return

            try:
                os.rmdir(empty)
            except OSError, (ecode, emsg):
                raise TreeError('Error removing empty directory %s: %s' % (empty, emsg))

            # Try to remove parent empty directory
            empty = os.path.dirname(empty)


class Tree(IterableTrackFolder):
    """Tree

    Audio file tree

    """

    def __init__(self, path):
        IterableTrackFolder.__init__(self, path, 'files')
        self.paths = {}
        self.empty_dirs = []
        self.relative_dirs = []

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

    def __cmp_file_path__(self, a, b):
        if a[0] != b[0]:
            return cmp(a[0], b[0])
        return cmp(a[1], b[1])

    def load(self):
        """Load the albums and songs in the tree"""

        if not os.path.isdir(self.path):
            raise TreeError('Not a directory: %s' % self.path)

        self.log.debug('load tree: %s' % self.path)
        start = long(time.mktime(time.localtime()))

        IterableTrackFolder.load(self)
        self.paths = {}
        self.empty_dirs = []
        self.relative_dirs = []
        for (root, dirs, files) in os.walk(self.path, topdown=True):
            if files:
                self.files.extend((root, x) for x in files)
                for x in files:
                    self.paths[os.path.join(root, x)] = True
            elif not dirs:
                self.empty_dirs.append(root)

        self.relative_dirs = set(self.relative_path(x[0]) for x in self.files)
        self.files.sort(lambda x, y: self.__cmp_file_path__(x, y))

        stop = long(time.mktime(time.localtime()))
        self.log.debug('loaded %d files in %d seconds' % (len(self.files), (stop-start)))

    def filter_tracks(self, regexp=None, re_path=True, re_file=True, as_tracks=False):
        if not len(self.files):
            self.load()

        tracks = filter(lambda f: match_codec(f[1]), self.files)
        if regexp is not None:
            if not re_file and not re_path:
                raise TreeError('No matches if both re_file and re_path are False')
            if isinstance(regexp, basestring):
                regexp = re.compile(regexp)
            tracks = filter(lambda t:
                re_path and regexp.match(t[0]) or re_file and regexp.match(t[1]),
                tracks
            )

        if as_tracks:
            return [Track(os.path.join(t[0], t[1])) for t in tracks]
        else:
            return tracks

    @property
    def directories(self):
        return set(normalized(os.path.dirname(x)) for x in self.paths.keys())

    @property
    def realpaths(self):
        return dict((normalized(os.path.realpath(v)), True) for v in self.paths.keys())

    def contains(self, path):
        directory = os.path.dirname(path)
        filename = os.path.filename(path)

    def as_albums(self):
        if not self.has_been_iterated:
            self.load()
        return [Album(path) for path in sorted(set(d[0] for d in self.files))]

    def match(self, path):
        relative_path = self.relative_path(path)
        if not os.path.dirname(relative_path) in self.relative_dirs:
            return None


class Album(IterableTrackFolder):

    def __init__(self, path):
        IterableTrackFolder.__init__(self, path, 'files')
        self.metadata_files = []

    def __getitem__(self, item):
        item = IterableTrackFolder.__getitem__(self, item)
        return Track(os.path.join(*item))

    def load(self):
        IterableTrackFolder.load(self)
        for f in os.listdir(self.path):
            if match_codec(f) is not None:
                self.files.append((self.path, f))

            else:
                metadata = match_metadata(f)
                if not metadata:
                    continue

                self.metadata_files.append(
                    metadata.__class__(os.path.join(self.path, f))
                )

        self.files.sort()

    @property
    def mtime(self):
        return os.stat(self.path).st_mtime

    @property
    def ctime(self):
        return os.stat(self.path).st_ctime

    @property
    def atime(self):
        return os.stat(self.path).st_atime

    @property
    def metadata(self):
        if not self.has_been_iterated:
            self.load()
        return self.metadata_files

    @property
    def albumart(self):
        if not len(self.metadata):
            return None

        for m in self.metadata:
            if isinstance(m, CoverArt):
                return AlbumArt(m.path)
        return None

    def copy_metadata(self, target):
        if isinstance(target, basestring):
            target = Album(target)

        if not os.path.isdir(target.path):
            try:
                os.makedirs(target.path)
            except OSError, (ecode, emsg):
                raise TreeError('Error creating directory %s: %s' % (target.path, emsg))

        for m in self.metadata:
            dst_path = os.path.join(target.path, os.path.basename(m.path))

            try:
                shutil.copyfile(m.path, dst_path)
            except OSError, (ecode, emsg):
                self.script.exit(1, 'Error writing %s: %s' % (dst_path, emsg))

        target.load()
        albumart = target.albumart
        if target.albumart:
            for track in target:
                tags = track.tags
                if not tags.supports_albumart:
                    self.log.debug('no albumart support: %s' % track.path)
                    continue
                if tags.set_albumart(albumart):
                    self.log.debug('albumart: %s' % track)
                    tags.save()


class MetaDataFile(object):
    """MetaDataFile

    Metadata files, like album artwork, booklets and vendor specific
    analysis files.

    """

    def __init__(self, path, metadata=None):
        self.config = MusaConfigDB()
        if metadata is None:
            metadata = match_metadata(path)
            if metadata is None:
                raise TreeError('Not a metadata file: %s' % path)

        self.path = path_string(path)
        self.extension = os.path.splitext(self.path)[1][1:].lower()
        if self.extension == '':
            self.extension = None
        self.metadata = metadata

    def __repr__(self):
        return self.extension is not None and self.extension or 'metadata'


class Track(MusaFileFormat):
    """Track

    Audio file track

    """

    def __init__(self, path):
        MusaFileFormat.__init__(self, path)
        self.prefixes = TreePrefixes()
        if self.codec is None:
            raise TreeError('Not a music file: %s' % self.path)
        self.tags_loaded = False
        self.file_tags = None

    @property
    def tags(self):
        if not self.tags_loaded:
            try:
                self.file_tags = Tags(self.path, fileformat=self)
                self.tags_loaded = True
            except TagError, emsg:
                raise TreeError('Error loading tags: %s' % emsg)

        return self.file_tags

    @property
    def relative_path(self):
        return self.prefixes.relative_path(os.path.realpath(self.path))

    @property
    def extension(self):
        return os.path.splitext(self.path)[1][1:]

    @property
    def album(self):
        return Album(os.path.dirname(self.path))

    @property
    def tracknumber_and_title(self):
        filename = os.path.splitext(os.path.basename(self.path))[0]
        try:
            tracknumber, title = filename.split(None, 1)
            tracknumber = int(tracknumber)
        except ValueError:
            tracknumber = None
            title = filename

        return tracknumber, title

    def get_album_tracks(self):
        path = os.path.dirname(self.path)
        extensions = CODECS[self.codec]['extensions']
        tracks = []

        for t in os.listdir(path):
            if os.path.splitext(t)[1][1:] not in extensions:
                continue
            tracks.append(Track(os.path.join(path, t)))

        return tracks

    def get_decoder_command(self, wav_path=None):
        if wav_path is None:
            wav_path = '%s.wav' % os.path.splitext(self.path)[0]
        if wav_path == self.path:
            raise TreeError('Trying to encode to itself')

        try:
            decoder = self.get_available_decoders()[0]
        except IndexError:
            raise TreeError('No available decoders for %s' % self.path)

        decoder = decoder.split()
        decoder[decoder.index('OUTFILE')] = wav_path
        decoder[decoder.index('FILE')] = self.path
        return decoder

    def get_encoder_command(self, wav_path=None):
        if wav_path is None:
            wav_path = '%s.wav' % os.path.splitext(self.path)[0]
        if wav_path == self.path:
            raise TreeError('Trying to encode to itself')

        try:
            encoder = self.get_available_encoders()[0]
        except IndexError:
            raise TreeError('No available encoders for %s' % self.path)

        encoder = encoder.split()
        encoder[encoder.index('OUTFILE')] = self.path
        encoder[encoder.index('FILE')] = wav_path
        return encoder
