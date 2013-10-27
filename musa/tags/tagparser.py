# coding=utf-8
"""Tag abstraction

Tag metadata reader and writer classes

"""

import os
import base64
import json
import logging
from datetime import datetime, timedelta

from musa import normalized
from musa.formats import MusaFileFormat
from musa.tags import TagError
from musa.log import MusaLogger
from musa.tags.constants import STANDARD_TAG_ORDER
from musa.tags.xmltag import XMLTags, XMLTagError
from musa.tags.albumart import AlbumArt, AlbumArtError

__all__ = ['aac', 'flac', 'mp3', 'vorbis']

logger = logging.getLogger(__file__)

# Format parsers for printing out various year tag formats supported internally
YEAR_FORMATTERS = [
    lambda x: unicode('%s'% int(x), 'utf-8'),
    lambda x: unicode('%s'% datetime.strptime(x, '%Y-%m-%d').strftime('%Y'), 'utf-8'),
    lambda x: unicode('%s'% datetime.strptime(x, '%Y-%m-%dT%H:%M:%SZ').strftime('%Y'), 'utf-8'),
]

class TagParser(dict):

    """
    Parent class for tag parser implementations
    """
    def __init__(self, codec, path, tag_map=None):
        dict.__init__(self)
        self.codec = codec
        self.path = normalized(os.path.realpath(path))
        self.tag_map = tag_map is not None and tag_map or {}
        self.entry = None
        self.modified = False

        self.albumart_obj = None
        self.supports_albumart = False

    def __getattr__(self, attr):
        try:
            return self[attr]
        except KeyError:
            pass
        raise AttributeError('No such TagParser attribute: %s' % attr)

    def __getitem__(self, item):
        """
        Return tags formatted to unicode, decimal.Decimal or
        other supported types.
        Does not include albumart images, which are accessed
        via self.albumart attribute
        """
        fields = self.__tag2fields__(item)
        for field in fields:
            if field not in self.entry:
                continue
            tag = self.entry[field]
            if not isinstance(tag, list):
                tag = [tag]
            values = []
            for value in tag:
                if not isinstance(value, unicode):
                    if isinstance(value, int):
                        value = unicode('%d' % value)
                    else:
                        try:
                            value = unicode(value, 'utf-8')
                        except UnicodeDecodeError, emsg:
                            raise TagError('Error decoding %s tag %s: %s' % (self.path, field, emsg))
                values.append(value)
            return values
        raise KeyError('No such tag: %s' % fields)

    def __setitem__(self, item, value):
        if isinstance(item, AlbumArt):
            try:
                self.albumart_obj.import_albumart(value)
            except AlbumArtError, emsg:
                raise TagError('Error setting albumart: %s' % emsg)
        self.set_tag(item, value)

    def __delitem__(self, item):
        fields = self.__tag2fields__(item)
        for tag in fields:
            if tag not in self.entry.keys():
                continue
            logger.debug('%s: remove tag %s' % (self.path, item))
            del self.entry[tag]
            self.modified = True

    def __tag2fields__(self, tag):
        """
        Resolve tag name to internal parser field
        """
        for name, tags in self.tag_map.items():
            if tag == name:
                return tags
        return [tag]

    def __field2tag__(self, field):
        """
        Resolve internal parser field to tag name
        """
        for name, tags in self.tag_map.items():
            # Can happen if name is internal reference: ignore here

            if tags is None:
                continue

            if field in tags:
                return name

        return field

    def __flatten_tag__(self, tag):
        """
        Flatten and mangle tag values to standard formats
        """
        try:
            value = self[tag]
        except KeyError:
            return None

        if isinstance(value, list):
            if len(value) == 0:
                return None
            if isinstance(value[0], basestring):
                value = value[0]

        # Skip non-string tags
        if not isinstance(value, basestring):
            return None

        if tag=='year':
            # Try to clear extra date details from year
            for fmt in YEAR_FORMATTERS:
                try:
                    return fmt(value)
                except ValueError, emsg:
                    pass

        return value

    def __repr__(self):
        return '%s: %s' % (self.codec, self.path)

    @property
    def mtime(self):
        return os.stat(self.path).st_mtime

    @property
    def atime(self):
        return os.stat(self.path).st_atime

    @property
    def ctime(self):
        return os.stat(self.path).st_ctime

    @property
    def albumart(self):
        if not self.supports_albumart or not self.albumart_obj:
            return None
        return self.albumart_obj

    def set_albumart(self, albumart):
        if not self.supports_albumart:
            raise TagError('Format does not support albumart')
        return self.albumart.import_albumart(albumart)

    def remove_tag(self, item):
        if not self.has_key(item):
            raise TagError('No such tag: %s' % item)
        del self[tag]

    def get_tag(self, item):
        """
        Return tag from file. Raises TagError if tag is not found
        If tag has multiple values, only first one is returned.
        """
        if not self.has_key(item):
            raise TagError('No such tag: %s' % item)

        value = self.__flatten_tag__(item)
        if value is None:
            raise TagError('No such string tag: %s' % item)

        return value

    def set_tag(self, item, value):
        """
        Sets the tag item to given value.
        Must be implemented in child class, this raises
        NotImplementedError
        """
        raise NotImplementedError('Must implement set_tag in child')

    def get_raw_tags(self):
        """
        Get internal presentation of tags
        """
        return self.entry.items()

    def get_unknown_tags(self):
        """
        Must be implemented in child if needed: return empty list here
        """
        return []

    def sort_keys(self, keys):
        """
        Sort keys with STANDARD_TAG_ORDER list
        """
        values = []
        for k in STANDARD_TAG_ORDER:
            if k in keys:
                values.append(k)
        for k in keys:
            if k not in STANDARD_TAG_ORDER:
                values.append(k)
        return values

    def has_key(self, key):
        """
        Test if given key is in tags
        """
        keys = self.__tag2fields__(key)
        for k in keys:
            if k in self.entry.keys():
                return True
        return False

    def keys(self):
        """
        Return file tag keys mapped with tag_map.
        """
        return self.sort_keys(
            [self.__field2tag__(k) for k in self.entry.keys()]
        )

    def items(self):
        """
        Return tag, value pairs using tag_map keys.
        If tag has multiple values, only first one is returned.
        """
        tags = []
        for tag in self.keys():
            value = self.__flatten_tag__(tag)
            if value is None:
                continue
            tags.append((tag, value))
        return tags

    def values(self):
        """
        Return tag values from entry.
        If tag has multiple values, only first one is returned.
        """
        values = []
        for tag in self.keys():
            value = self.__flatten_tag__(tag)
            if value is None:
                continue
            values.append(value)
        return values

        return [self[k] for k, v in self.keys()]

    def as_dict(self):
        """
        Return tags as dictionary
        """
        return dict(self.items())

    def as_xml(self):
        """
        Return tags formatted as XML
        """
        return XMLTags(self.as_dict())

    def to_json(self, indent=2):
        """
        Return tags formatted as json
        """
        stat = os.stat(self.path)
        return json.dumps(
            {
                'filename': self.path,
                'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'size': stat.st_size,
                'tags': [{'tag':k, 'value':v} for k, v in self.items()]
            },
            ensure_ascii=False,
            indent=indent,
            sort_keys=True
        )

    def get_unknown_tags(self):
        """
        Must be implemented in child if needed: return empty list here
        """
        return []

    def update_tags(self, data):
        if not isinstance(data, dict):
            raise TagError('Updated tags must be a dictionary instance')
        for k, v in data.items():
            self.set_tag(k, v)
        return self.modified

    def replace_tags(self, data):
        if not isinstance(data, dict):
            raise TagError('Updated tags must be a dictionary instance')
        for k, v in self.items():
            if k not in data.keys():
                self.remove_tag(k)
        return self.update_tags(data)

    def remove_tags(self, tags):
        """
        Remove given list of tags from file
        """
        for tag in tags:
            if tag not in self.keys():
                continue
            del self[tag]
        if self.modified:
            self.save()

    def clear_tags(self):
        """
        Remove all tags from file
        """
        for tag in self.keys():
            del self[tag]
        if self.modified:
            logger.debug('Cleared all tags from file')
            self.save()

    def remove_unknown_tags(self):
        """
        Remove any tags which we don't know about.
        """
        for tag in self.unknown_tags:
            del self[tag]
        if self.modified:
            self.save()

    def save(self):
        """
        Save tags to file.
        """
        try:
            for attr in ['track_numbering', 'disk_numbering']:
                try:
                    tag = getattr(self, attr)
                    tag.save_tag()
                except ValueError, emsg:
                    logger.debug('Error processing %s: %s' % (attr, emsg))

            if not self.modified:
                logger.debug('tags not modified')
                return

            # TODO - replace with copying of file to new inode
            self.entry.save()
        except OSError, (ecode, emsg):
            raise TagError(emsg)

        except IOError, (ecode, emsg):
            raise TagError(emsg)

class TrackAlbumart(object):

    """
    Parent class for common albumart operations
    """
    def __init__(self, track):
        self.track = track
        self.modified = False
        self.albumart = None

    def __repr__(self):
        return self.albumart.__repr__()

    @property
    def info(self):
        if self.albumart is None:
            return {}
        self.albumart.get_info()

    @property
    def defined(self):
        """
        Returns True if albumart is defined, False otherwise
        """
        if self.albumart is None:
            return False
        return True

    def as_base64_tag(self):
        """
        Return albumart image data as base64_tag tag
        """
        if self.albumart is None:
            raise TagError('Albumart is not loaded')
        return base64_tag(base64.b64encode(self.albumart.dump()))

    def import_albumart(self, albumart):
        """
        Parent method to set albumart tag. Child class must
        implement actual embedding of the tag to file.
        """
        if not isinstance(albumart, AlbumArt):
            raise TagError('Albumart must be AlbumArt instance')
        if not albumart.is_loaded:
            raise TagError('Albumart to import is not loaded with image.')
        self.albumart = albumart

    def save(self, path):
        """
        Save current albumart to given pathname
        """
        if self.albumart is None:
            raise TagError('Error saving albumart: albumart is not loaded')
        self.albumart.save(path)


class TrackNumberingTag(object):

    """
    Parent class for processing track numbering info, including track and
    disk numbers and total counts.

    Fields should be set and read from attributes 'value' and 'total'
    """
    def __init__(self, track, tag):
        self.track = track
        self.tag = tag
        self.f_value = None
        self.f_total = None

    def __repr__(self):
        if self.total is not None:
            return '%d/%d' % (self.value, self.total)
        elif self.value is not None:
            return '%d' % (self.value)
        else:
            return None

    def __getattr__(self, attr):
        if attr == 'value':
            return self.f_value
        if attr == 'total':
            return self.f_total
        raise AttributeError('No such TrackNumberingTag attribute: %s' % attr)

    def __setattr__(self, attr, value):
        if attr in ['value', 'total']:
            if isinstance(value, list):
                value = value[0]
            try:
                if value is not None:
                    value = int(value)
            except ValueError:
                raise TagError('TrackNumberingTag values must be integers')
            except TypeError:
                raise TagError('TrackNumberingTag values must be integers')
            if attr == 'value':
                self.f_value = value
            if attr == 'total':
                self.f_total = value
        else:
            object.__setattr__(self, attr, value)

    def save_tag(self):
        """
        Export this numbering information back to file tags.

        If value is None, ignore both values without setting tag.
        If total is None but value is set, set total==value.
        """
        raise NotImplementedError('save_tag must be implemented in child class')

def Tags(path, fileformat=None):
    """
    Loader for file metadata tags. Tag reading and writing for various
    file formats is implemented by tag formatter classes in module
    soundforest.tags.formats, initialized automatically by this class.
    """
    if not os.path.isfile(path):
        raise TagError('No such file: %s' % path)
    path = normalized(os.path.realpath(path))

    if fileformat is None:
        fileformat = MusaFileFormat(path)

    if not isinstance(fileformat, MusaFileFormat):
        raise TagError('File format must be MusaFileFormat instance')

    fileformat = fileformat
    if fileformat.is_metadata:
        raise TagError('Attempting to load audio tags from metadata file')

    if fileformat.codec is None:
        raise TagError('Unsupported audio file: %s' % path)

    tag_parser = fileformat.get_tag_parser()
    if tag_parser is None:
        return None

    return tag_parser(fileformat.codec, path)
