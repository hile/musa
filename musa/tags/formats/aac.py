# coding=utf-8
"""
AAC file tag parser
"""

import base64,struct

from mutagen.mp4 import MP4,MP4Cover,MP4StreamInfoError,MP4MetadataValueError

from musa.tags import TagError
from musa.tags.tagparser import TagParser,TrackNumberingTag,TrackAlbumart
from musa.tags.albumart import AlbumArt,AlbumArtError

# Albumart filed processing
AAC_ALBUMART_TAG = 'covr'
AAC_ALBUMART_PIL_FORMAT_MAP = {
    'JPEG':     MP4Cover.FORMAT_JPEG,
    'PNG':      MP4Cover.FORMAT_PNG
}

AAC_STANDARD_TAGS = {
    'album_artist':         ['aART'],
    'artist':               ['\xa9ART'],
    'composer':             ['\xa9wrt'],
    'conductor':            ['cond'],
    'orchestra':            ['orch'],
    'performers':           ['ense'],
    'album':                ['\xa9alb'],
    'title':                ['\xa9nam'],
    'genre':                ['\xa9gen'],
    'comment':              ['\xa9cmt'],
    'note':                 ['note'],
    'description':          ['desc'],
    'location':             ['loca'],
    'year':                 ['\xa9day'],
    'bpm':                  ['tmpo'],
    'rating':               ['rati'],
    'label':                ['labe'],
    'copyright':            ['cprt'],
    'license':              ['lice'],
    'sort_album_artist':    ['soaa'],
    'sort_artist':          ['soar'],
    'sort_composer':        ['soco'],
    'sort_performers':      ['sopr'],
    'sort_show':            ['sosn'],
    'sort_album':           ['soal'],
    'sort_title':           ['sonm'],
}

# Internal program tags for itunes. Ignored by current code
ITUNES_TAG_MAP = {

    # Boolean flag indicating if track is part of compilation, useful
    # but buggy even with iTunes 10.x, I don't recommend using this:
    # set album_artist to 'Various Artists' instead.
    'compilation':          ['cpil'],
    # iTunes grouping flag
    'grouping':             ['\xa9grp'],
    # Indicates the encoder command used to encode track
    'encoder':              ['\xa9too','enco'],
    # Another way iTunes stores tool info
    'itunes_tool':          ['----:com.apple.iTunes:tool'],
    # iTunes encoder and normalization data
    'itunes_encoder':       ['----:com.apple.iTunes:cdec'],
    'itunes_normalization': ['----:com.apple.iTunes:iTunNORM'],
    # XML info for song
    'itunes_movi':          ['----:com.apple.iTunes:iTunMOVI'],
    # NO idea what this is
    'itunes_smbp':          ['----:com.apple.iTunes:iTunSMPB'],
    # iTunes store purchase details
    'purchase_date':        ['purd'],
    'purchaser_email':      ['apID'],
    # Tags for video shows
    'video_show':           ['tvsh'],
    'video_episode':        ['tven'],
    # XID is internal itunes metadata reference
    'xid':                  ['xid'],
}

AAC_UNOFFICIAL_TAGS = {
    # Musicbrainz ID reference
    'musicbrainz_id':       ['musi'],
}

# These values are (value,value) pairs in metadata
AAC_INTEGER_TUPLE_TYPES = [ 'trkn', 'disk' ]

# Placeholder to write lambda functions to process specific tags if needed
AAC_TAG_FORMATTERS = {
    #'tempo':    lambda x: int(x),
}

class AACAlbumArt(TrackAlbumart):
    """
    Thin wrapper to process AAC object albumart files

    Technically supports setting albumart to other tags than
    standard AAC_ALBUMART_TAG. Don't do this, not tested.
    """
    def __init__(self,track,tag=AAC_ALBUMART_TAG):
        if not isinstance(track,aac):
            raise TagError('Track is not instance of aac')
        TrackAlbumart.__init__(self,track)
        self.tag = AAC_ALBUMART_TAG

        if not self.track.entry.has_key(self.tag):
            return
        try:
            albumart = AlbumArt()
            albumart.import_data(self.track.entry[self.tag][0])
        except AlbumArtError,emsg:
            raise TagError('Error reading AAC albumart tag: %s' % emsg)
        self.albumart = albumart

    def import_albumart(self,albumart):
        """
        Imports albumart object to the file tags.

        Sets self.track.modified to True
        """
        TrackAlbumart.import_albumart(self,albumart)

        try:
            img_format = AAC_ALBUMART_PIL_FORMAT_MAP[self.albumart.get_fileformat()]
        except KeyError:
            raise TagError('Unsupported albumart format %s' % self.albumart.get_fileformat() )
        try:
            tag = MP4Cover(data=self.albumart.dump(),imageformat=img_format)
        except MP4MetadataValueError,emsg:
            raise TagError('Error encoding albumart: %s' % emsg)

        if self.track.entry.has_key(self.tag):
            if self.track.entry[self.tag] != [tag]:
                del self.track.entry[self.tag]
            else:
                return False
        self.track.entry[self.tag] = [tag]
        self.track.modified = True
        return self.track.modified

class AACIntegerTuple(TrackNumberingTag):
    """
    AAC field for ('item','total items') type items in tags.
    Used for track and disk numbering
    """
    def __init__(self,track,tag):
        TrackNumberingTag.__init__(self,track,tag)

        if not self.track.entry.has_key(self.tag):
            return

        self.value,self.total = self.track.entry[self.tag][0]

    def delete_tag(self):
        self.value = None
        self.total = None
        if self.tag in self.track.entry.keys():
            del self.track.entry[self.tag]
            self.track.modified = True

    def save_tag(self):
        """
        Export this numbering information back to AAC tags.

        If value is None, ignore both values without setting tag.
        If total is None but value is set, set total==value.
        """
        if self.f_value is None:
            return
        value = self.value
        total = self.total
        if total is None:
            total = value
        if total < value:
            raise ValueError('Total is smaller than number')
        self.track.entry[self.tag] = [(value,total)]
        self.track.modified = True

class aac(TagParser):
    """
    Class for processing AAC file tags
    """
    def __init__(self,codec,path):
        TagParser.__init__(self,codec,path,tag_map=AAC_STANDARD_TAGS)

        try:
            self.entry = MP4(self.path)
        except IOError,e:
            raise TagError('Error opening %s: %s' % (path,str(e)))
        except MP4StreamInfoError,e:
            raise TagError('Error opening %s: %s' % (path,str(e)))
        except struct.error:
            raise TagError('Invalid tags in %s' % path)
        except RuntimeError,e:
            raise TagError('Error opening %s: %s' % (path,str(e)))

        self.supports_albumart = True
        self.albumart_obj = AACAlbumArt(self)
        self.track_numbering = AACIntegerTuple(self,'trkn')
        self.disk_numbering = AACIntegerTuple(self,'disk')

    def __getitem__(self,item):
        if item == 'tracknumber':
            return [unicode('%d' % self.track_numbering.value)]
        if item == 'totaltracks':
            return [unicode('%d' % self.track_numbering.total)]
        if item == 'disknumber':
            return [unicode('%d' % self.disk_numbering.value)]
        if item == 'totaldisks':
            return [unicode('%d' % self.disk_numbering.total)]
        if item == 'unknown_tags':
            keys = []
            for tag in self.entry.keys():
                if tag in AAC_STANDARD_TAGS.values():
                    continue
                if tag in ITUNES_TAG_MAP.values():
                    continue
                if tag in AAC_UNOFFICIAL_TAGS.values():
                    continue
                keys.append(tag)
            return keys
        return TagParser.__getitem__(self,item)

    def __delitem__(self,item):
        if item in ['tracknumber','totaltracks']:
            return self.track_numbering.delete_tag()
        if item in ['disknumber','totaldisks']:
            return self.dsk_numbering.delete_tag()
        return TagParser.__delitem__(self,item)

    def set_tag(self,item,value):
        """
        Set given tag to correct type of value in tags.

        Normal tag values in AAC tags are always a list
        and you can pass this function a list to set all values.

        Tracknumber, totaltracks, disknumber and totaldisks
        attributes must be integers.

        Existing tag value list is replaced.
        """
        if item == 'tracknumber':
            self.track_numbering.value = value
        elif item == 'totaltracks':
            self.track_numbering.total = value
        elif item == 'disknumber':
            self.disk_numbering.value = value
        elif item == 'totaldisks':
            self.disk_numbering.total = value
        else:
            if not isinstance(value,list):
                value = [value]

            tags = self.__tag2fields__(item)
            item = tags[0]
            for tag in tags[1:]:
                if self.entry.has_key(tag):
                    del self.entry[tag]

            entries =[]
            for v in value:
                if AAC_TAG_FORMATTERS.has_key(item):
                    formatted = AAC_TAG_FORMATTERS[item](v)
                    entries.append(formatted)
                else:
                    if not isinstance(v,unicode):
                        v = unicode(v,'utf-8')
                    entries.append(v)
            self.entry[item] = entries

        self.modified = True

    def keys(self):
        """
        Return tag names sorted with self.sort_keys()

        Itunes internal tags are ignored from results
        """
        keys = TagParser.keys(self)
        if 'trkn' in keys:
            keys.extend(['tracknumber','totaltracks'])
            keys.remove('trkn')
        if 'disk' in keys:
            keys.extend(['disknumber','totaldisks'])
            keys.remove('disk')
        if 'covr' in keys:
            keys.remove('covr')
        for itunes_tags in ITUNES_TAG_MAP.values():
            for tag in itunes_tags:
                if tag in keys:
                    keys.remove(tag)
        return self.sort_keys(keys)

    def save(self):
        """
        Save AAC tags to the file
        """
        for attr in ['track_numbering','disk_numbering']:
            try:
                tag = getattr(self,attr)
                tag.save_tag()
            except ValueError,emsg:
                self.log.debug('Error processing %s: %s' % (attr,emsg))
        try:
            TagParser.save(self)
        except MP4MetadataValueError,emsg:
            raise TagError(emsg)
        self.modified = False
