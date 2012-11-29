#!/usr/bin/env python
"""
Abstraction for album art image format processing
""" 

import os,requests,logging,StringIO
from PIL import ImageFile

PIL_EXTENSION_MAP = {
    'JPEG':     'jpg',
    'PNG':      'png',
}

PIL_MIME_MAP = {
    'JPEG':     'image/jpeg',
    'PNG':      'image/png',
}

class AlbumArtError(Exception):
    """
    Exception thrown by errors in file metadata, parameters or 
    file permissiosns.
    """
    def __str__(self):  
        return self.args[0]

class AlbumArt(object):
    """
    Class to parse albumart image files from tags and files
    """
    def __init__(self,path=None):
        self.__image = None
        self.__mimetype = None
        if path is not None:
            self.import_file(path)

    def import_data(self,data):
        """
        Import albumart from metadata tag or database as bytes
        """
        self.__parse_image(data)

    def import_file(self,path):
        """
        Import albumart from file
        """
        if not os.path.isfile(path):
            raise AlbumArtError('No such file: %s' % path)
        if not os.access(path,os.R_OK):
            raise AlbumArtError('No permissions to read file: %s' % path)
        self.__parse_image(open(path,'r').read())

    def __parse_image(self,data):
        """
        Load the image from data with PIL
        """
        try:
            parser = ImageFile.Parser()
            parser.feed(data)
            self.__image = parser.close()
        except IOError:
            raise AlbumArtError('Error parsing albumart image data')
        try:
            self.__mimetype = PIL_MIME_MAP[self.__image.format]
        except KeyError:
            self.__image = None
            raise AlbumArtError(
                'Unsupported PIL image format: %s' % self.__image.format
            )

        if self.__image.mode != 'RGB':
            self.__image = self.__image.convert('RGB')

    def __repr__(self):
        """
        Returns text description of image type and size
        """
        if not self.is_loaded:
            return 'Uninitialized AlbumArt object.'
        return '%(mime)s %(bytes)d bytes %(width)dx%(height)d' % self.info

    def __getattr__(self,attr):
        """
        Attributes created on the fly and returned:
        image       PIL image
        format      PIL image format
        info         dictinary containing image information:
            type    always 3 (mp3 header type for album cover)
            mime    image mime type
            depth   image bit depth
            width   image width
            height  image height
            colors  always 0
        """
        if attr == 'is_loaded':
            if self.__image is None:
                return False
            return True
        if attr in ['image','format']:
            if self.__image is None:
                raise AlbumArtError('AlbumArt not yet initialized.')
            if attr == 'image':
                return self.__image
            elif attr == 'format': 
                return self.__image.format
        if attr == 'info':
            if self.__image is None:
                raise AlbumArtError('AlbumArt not yet initialized.')
            colors = self.__image.getcolors()
            if colors is None:
                colors = 0
            return {
                'type': 3, # Album cover
                'mime': self.__mimetype,
                'bytes': len(self.dump()),
                'depth': self.__image.bits,
                'width': int(self.__image.size[0]),
                'height': int(self.__image.size[1]),
                'colors': colors,
            }
        raise AttributeError('No such AlbumArt attribute: %s' % attr)

    def __unicode__(self):
        """
        Returns file format and size as unicode string
        """
        if not self.is_loaded:
            return unicode('Uninitialized AlbumArt object')
        return unicode('%s file %d bytes' % (self.format,len(self)))

    def __len__(self):
        """
        Returns PIL image length as string
        """
        if not self.is_loaded:
            return 0
        return len(self.image.tostring())

    def dump(self):
        """
        Returns bytes from the image with StringIO.StringIO read() call
        """
        if not self.is_loaded:
            raise AlbumArtError('AlbumArt not yet initialized.')
        s = StringIO.StringIO()
        self.__image.save(s,self.format)
        s.seek(0)
        return s.read()

    def fetch(self,url):
        res = requests.get(url)
        if r.status_code!=200:
            raise AlbumArtError('Error fetching url %s (returns %s' % (url,r.status_code))
        if 'content-type' not in res.headers:
            raise AlbumArtError('Response did not include content type header')
        try:
            content_type = res.headers['content_type']
            (prefix,extension) = content_type.split('/',1)
            if prefix!='image':
                raise AlbumArtError(
                    'Content type of data is not supported: %s' % content_type
                )
        except ValueError:
            raise AlbumArtError(
                'Error parsing content type %s' % res.headers['content_type']
            )
        return self.import_data(r.content)

    def save(self,path,format=None):
        """
        Saves the image data to given target file.

        If target filename exists, it is removed before saving.
        """
        if not self.is_loaded:
            raise AlbumArtError('AlbumArt not yet initialized.')
        if format is None:
            format = self.format
        if os.path.isfile(path):
            try:
                os.unlink(path)
            except IOError,(ecode,emsg):
                raise AlbumArtError(
                    'Error removing existing file %s: %s' % (path,emsg)
                )
        try:
            self.__image.save(path,format)
        except IOError,emsg:
            raise AlbumArtError('Error saving %s: %s' % (path,emsg))

