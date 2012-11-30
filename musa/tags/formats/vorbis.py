# coding=utf-8
"""
Vorbis file tag parser
"""

from mutagen.oggvorbis import OggVorbis,OggVorbisHeaderError

from musa.tags import TagError
from musa.tags.tagparser import TagParser,TrackNumberingTag
from musa.tags.albumart import AlbumArt,AlbumArtError

VORBIS_ALBUMART_TAG = 'METADATA_BLOCK_PICTURE'

VORBIS_STANDARD_TAGS = {
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
    'year':                 ['DATE'],
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

VORBIS_REPLAYGAIN_TAGS = {
    'album_gain':           ['REPLAYGAIN_ALBUM_GAIN'],
    'album_peak':           ['REPLAYGAIN_ALBUM_PEAK'],
    'track_gain':           ['REPLAYGAIN_TRACK_GAIN'],
    'track_peak':           ['REPLAYGAIN_TRACK_PEAK'],
}

VORBIS_TAG_FORMATTERS = {

}

VORBIS_EXTRA_TAGS = {
    'isrc':                 ['ISRC'],

}

class VorbisNumberingTag(TrackNumberingTag):
    """
    Vorbis tags for storing track or disk numbers.
    The tag can be either a single number or two numbers separated by /
    If total is given, the value must be integer.
    """
    def __init__(self,track,tag):
        TrackNumberingTag.__init__(self,track,tag)
        if not isinstance(track,vorbis):
            raise TagError('Track is not instance of vorbis')

        if not self.track.entry.has_key(self.tag):
            return

        value = self.track.entry[self.tag]
        try:
            value,total = value[0].split('/',1)
        except ValueError:
            total = None
        self.value = value
        self.total = total

    def save_tag(self):
        """
        Set new numbering information to vorbis tags, marking file
        dirty to require saving but not saving tags.
        """
        self.track.entry[self.tag] = '%s' % self.__repr__()
        self.track.modified = True

class vorbis(TagParser):
    """
    Class for processing Ogg Vorbis file tags
    """
    def __init__(self,codec,path):
        TagParser.__init__(self,codec,path,tag_map=VORBIS_STANDARD_TAGS)

        try:
            self.entry = OggVorbis(path)
        except IOError,e:
            raise TagError('Error opening %s: %s' % (path,str(e)))
        except OggVorbisHeaderError,e:
            raise TagError('Error opening %s: %s' % (path,str(e)))

        self.albumart_obj = None
        self.track_numbering = VorbisNumberingTag(self,'TRACKNUMBER')
        self.disk_numbering = VorbisNumberingTag(self,'DISKNUMBER')

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

        if VORBIS_ALBUMART_TAG in [x.upper() for x in keys]:
            keys.remove(VORBIS_ALBUMART_TAG)
        for replaygain_tag_fields in VORBIS_REPLAYGAIN_TAGS.values():
            for tag in replaygain_tag_fields:
                if tag in keys:
                    keys.remove(tag)
        return [x.lower() for x in self.sort_keys(keys)]

    def set_tag(self,item,value):
        """
        All vorbis tags are unicode strings, and there can be multiple
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
            if VORBIS_TAG_FORMATTERS.has_key(item):
                entries.append(VORBIS_TAG_FORMATTERS[item](v))
            else:
                if not isinstance(v,unicode):
                    v = unicode(v,'utf-8')
                entries.append(v)
        self.entry[item] = entries
        self.modified = True
