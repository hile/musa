# coding=utf-8
"""FLAC tags

Flac file tag parser

"""

from mutagen.flac import FLAC
from mutagen.flac import Picture,FLACNoHeaderError

from musa.tags import TagError
from musa.tags.tagparser import TagParser,TrackNumberingTag,TrackAlbumart
from musa.tags.albumart import AlbumArt,AlbumArtError

FLAC_ALBUMART_TAG = 'METADATA_BLOCK_PICTURE'

FLAC_STANDARD_TAGS = {
    'album_artist':         ['ALBUM_ARTIST'],
    'artist':               ['ARTIST'],
    'composer':             ['COMPOSER'],
    'conductor':            ['CONDUCTOR'],
    'orchestra':            ['ORCHESTRA'],
    'performers':           ['PERFORMER'],
    'album':                ['ALBUM'],
    'title':                ['TITLE'],
    'tracknumber':          ['TRACKNUMBER'],
    'disknumber':           ['DISKNUMBER'],
    'genre':                ['GENRE'],
    'comment':              ['COMMENT'],
    'note':                 ['NOTE'],
    'description':          ['DESCRIPTION'],
    'location':             ['LOCATION'],
    'year':                 ['DATE','YEAR'],
    'bpm':                  ['BPM'],
    'rating':               ['RATING'],
    'label':                ['ORGANIZATION'],
    'copyright':            ['COPYRIGHT'],
    'license':              ['LICENSE'],
    'sort_album_artist':    ['SORT_ALBUM_ARTIST'],
    'sort_artist':          ['SORT_ARTIST'],
    'sort_composer':        ['SORT_COMPOSER'],
    'sort_performers':      ['SORT_PERFORMERS'],
    'sort_show':            ['SORT_SHOW'],
    'sort_album':           ['SORT_ALBUM'],
    'sort_title':           ['SORT_TITLE'],
}

FLAC_REPLAYGAIN_TAGS = {
    'album_gain':           ['REPLAYGAIN_ALBUM_GAIN'],
    'album_peak':           ['REPLAYGAIN_ALBUM_PEAK'],
    'track_gain':           ['REPLAYGAIN_TRACK_GAIN'],
    'track_peak':           ['REPLAYGAIN_TRACK_PEAK'],
}

FLAC_TAG_FORMATTERS = {

}

FLAC_EXTRA_TAGS = {
    'isrc':                 ['ISRC'],

}

class FLACAlbumart(TrackAlbumart):
    """
    Encoding of flac albumart to flac Picture tags
    """
    def __init__(self,track):
        if not isinstance(track,flac):
            raise TagError('Track is not instance of flac')
        TrackAlbumart.__init__(self,track)

        try:
            self.albumart = AlbumArt()
            self.albumart.import_data(self.track.entry.pictures[0].data)
        except IndexError:
            self.albumart = None
            return

    def import_albumart(self,albumart):
        """
        Imports albumart object to the file tags.

        Sets self.track.modified to True
        """
        TrackAlbumart.import_albumart(self,albumart)

        p = Picture()
        [setattr(p,k,v) for k,v in self.albumart.info.items()]
        self.track.entry.add_picture(p)
        self.track.modified = True

class FLACNumberingTag(TrackNumberingTag):
    """
    FLAC tags for storing track or disk numbers.
    The tag can be either a single number or two numbers separated by /
    If total is given, the value must be integer.
    """
    def __init__(self,track,tag):
        TrackNumberingTag.__init__(self,track,tag)

        if not self.track.entry.has_key(self.tag):
            return

        value = self.track.entry[self.tag]
        try:
            value,total = value[0].split('/',1)
        except ValueError:
            value = value[0]
            total = None
        self.value = value
        self.total = total

    def save_tag(self):
        """
        Set new numbering information to vorbis tags, marking file
        dirty to require saving but not saving tags.
        """
        value = self.__repr__()
        if value is not None:
            self.track.entry[self.tag] = '%s' % value
            self.track.modified = True

class flac(TagParser):
    """
    Class for processing Ogg FLAC file tags
    """
    def __init__(self,codec,path):
        TagParser.__init__(self,codec,path,tag_map=FLAC_STANDARD_TAGS)

        try:
            self.entry = FLAC(path)
        except IOError,e:
            raise TagError('Error opening %s: %s' % (path,str(e)))
        except FLACNoHeaderError,e:
            raise TagError('Error opening %s: %s' % (path,str(e)))

        self.albumart_obj = None
        self.track_numbering = FLACNumberingTag(self,'TRACKNUMBER')
        self.disk_numbering = FLACNumberingTag(self,'DISKNUMBER')

    def __getitem__(self,item):
        if item == 'tracknumber':
            return [unicode('%d' % self.track_numbering.value)]
        if item == 'totaltracks':
            return [unicode('%d' % self.track_numbering.total)]
        if item == 'disknumber':
            return [unicode('%d' % self.disk_numbering.value)]
        if item == 'totaldisks':
            return [unicode('%d' % self.disk_numbering.total)]
        return TagParser.__getitem__(self,item)

    def __field2tag__(self,field):
        return TagParser.__field2tag__(self,field.upper())

    def keys(self):
        """
        Return tag names sorted with self.sort_keys()
        """
        keys = TagParser.keys(self)
        if 'TOTALTRACKS' in keys:
            keys.remove('TOTALTRACKS')
        if 'TOTALDISKS' in keys:
            keys.remove('TOTALDISKS')
        if 'TRACKNUMBER' in [x.upper() for x in keys]:
            if self.track_numbering.total is not None:
                keys.append('totaltracks')
        if 'DISKNUMBER' in [x.upper() for x in keys]:
            if self.disk_numbering.total is not None:
                keys.append('totaldisks')
        if FLAC_ALBUMART_TAG in [x.upper() for x in keys]:
            keys.remove(FLAC_ALBUMART_TAG)
        for replaygain_tag_fields in FLAC_REPLAYGAIN_TAGS.values():
            for tag in replaygain_tag_fields:
                if tag in keys:
                    keys.remove(tag)
        return [x.lower() for x in self.sort_keys(keys)]

    def set_tag(self,item,value):
        """
        All flac tags are unicode strings, and there can be multiple
        tags with same name.
        We do special precessing for track and disk numbering.
        """
        if item == 'tracknumber':
            self.track_numbering.value = value
            return
        if item == 'totaltracks':
            self.track_numbering.total = value
            return
        if item == 'disknumber':
            self.disk_numbering.value = value
            return
        if item == 'totaldisks':
            self.disk_numbering.total = value
            return

        if not isinstance(value,list):
            value = [value]

        tags = self.__tag2fields__(item)
        item = tags[0]
        for tag in tags[1:]:
            if self.entry.has_key(tag):
                del self.entry[tag]

        entries =[]
        for v in value:
            if FLAC_TAG_FORMATTERS.has_key(item):
                entries.append(FLAC_TAG_FORMATTERS[item](v))
            else:
                if not isinstance(v,unicode):
                    v = unicode(v,'utf-8')
                entries.append(v)
        self.entry[item] = entries
        self.modified = True
