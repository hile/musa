"""
XML schema representation of audio file metadata tags
"""

from lxml import etree as ET
from lxml.etree import XMLSyntaxError
from lxml.builder import E

from musa.tags.constants import parsedate

class XMLTagError(Exception):
    def __str__(self):
        return self.args[0]

XML_EXPORT_FIELDS = [
    'path',
    'album_artist',
    'sort_artist',
    'artist',
    'sort_album',
    'album',
    'sort_title',
    'title',
    'genre',
    'bpm',
    'year',
    'tracknumber',
    'comment',
    'composer',
    'copyright',
    'xid',
]

def XMLTrackNumberField(details):
    if details.has_key('totaltracks'):
        node = E('tracknumber', track=details['tracknumber'], total=details['totaltracks'] )
    else:
        node = E('tracknumber', track=details['tracknumber'], )
    return node

def XMLTrackYear(details):
    value = parsedate(details['year'])
    if value is None:
        return None
    return E('year','%d'%value.tm_year)

XML_FIELD_CLASSES = {
    'tracknumber': XMLTrackNumberField,
    'year': XMLTrackYear,
}

class XMLTags(dict):
    def __init__(self,data):
        dict.__init__(self)
        self.tree = E('track')
        if isinstance(data,dict):
            self.update(data)

    def update(self,details):
        if not isinstance(details,dict):
            raise XMLTagError('Details must be dictionary')
        dict.update(self,details)
        for k in XML_EXPORT_FIELDS:
            if not k in self.keys():
                continue
            if k in XML_FIELD_CLASSES.keys():
                node = XML_FIELD_CLASSES[k](self)
                if node is not None:
                    self.tree.append(node)
            else:
                self.tree.append(E(k,self[k]))

    def tostring(self):
        return ET.tostring(tree,pretty_print=True)

class XMLTrackTree(object):
    def __init__(self):
        self.tracks =  E('tracks')
        self.tree = E('musa', self.tracks)

    def append(self,xmltags):
        if not isinstance(xmltags,XMLTags):
            raise XMLTagError('xmltags must be XMLTags instance')
        self.tracks.append(xmltags.tree)

    def tostring(self):
        self.tracks.set('total','%d' % len(self.tracks))
        return ET.tostring(self.tree,pretty_print=True)
