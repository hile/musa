"""
Common metadata file matches seen in music file directories.

Please note these classes are not used to open or process the metadata files:
this module is intended only for detecting the type of files.
"""

import os

# List of filenames we consider as albumart images. 
ARTWORK_PREFIXES = ['albumart','artwork','album','front','back','cover']
ARTWORK_FORMATS = ['jpg','jpeg','png','gif']

# Same for cover booklet filenames: rename these consistently in your library!
BOOKLET_FILENAMES = [ 'booklet.pdf' ]

# Apple OS/X system files we wish to ignore
OSX_SYSTEM_FILES = [
    '.com.apple.timemachine.supported',
    '.DS_Store','.DS Store'
]

class MetadataFileType(object):
    """
    Parent class for metadata file description classes.

    Attributes:
    description     Textual description for this metadata file type
    filenames       List of full filenames to match to this type of metadata
    extensions      List of file extensions to match to this type of metadata
    """
    def __init__(self,description,filenames=None,extensions=None):
        self.description = description
        self.filenames = filenames
        self.extensions = extensions

    def __repr__(self):
        """
        Returns the description string
        """
        return self.description

    def match(self,path):
        """
        Match given path to this metadata file type. Override in child class
        if you need more complicated logic.

        Returns true if the filename matches metadata type, False if not.
        """
        path = os.path.realpath(path)
        if self.filenames:
            if os.path.basename(path) in self.filenames:
                return True
        if self.extensions:
            (name,ext) = os.path.splitext(path)
            if name=='':
                return False 
            ext = ext[1:].lower()
            if ext in self.extensions:
                return True
        return False

class iTunesLP(MetadataFileType):
    """
    iTunes LP - directory of files
    """
    def __init__(self):
        MetadataFileType.__init__(self,'iTunes LP',filenames=[])

    def match(self,path):
        path = os.path.realpath(path)
        parts = path.split(os.sep)
        if os.path.isfile(path):
            parts = parts[:-1]
        for p in parts:
            if os.path.splitext(p)[1]=='.itlp':
                return True
        return False

class OSXSystemFile(MetadataFileType):
    """
    OS/X system metadata files not relevant for audio trees.
    """
    def __init__(self):
        MetadataFileType.__init__(self,'OS/X System file',
            filenames=OSX_SYSTEM_FILES
        )

class AbletonAnalysisFile(MetadataFileType):
    """
    Ableton track metadata files.
    """
    def __init__(self):
        MetadataFileType.__init__(self,'Ableton Live Track Metadata',
            extensions=['asd']
        )

class Booklet(MetadataFileType):
    """
    PDF format album booklet, as received from itunes.

    Right now, we expect the file to be renamed to booklet.pdf in same directory
    as the album. Someone else may add parser for PDF files in general if needed.
    """
    def __init__(self):
        MetadataFileType.__init__(self,'Album Cover Booklet',
            filenames=BOOKLET_FILENAMES, 
            extensions=['pdf']
        )

class CoverArt(MetadataFileType):
    """
    Coverart files stored to the album directory with music files.

    Static list of albumart filenames we process are defined in module sources.
    """
    def __init__(self):
        ARTWORK_NAMES = ['%s.%s'%(name,ext) \
            for name in ARTWORK_PREFIXES \
            for ext in ARTWORK_FORMATS
        ]
        MetadataFileType.__init__(self,'Album Artwork',
            filenames=ARTWORK_NAMES
        )

class Playlist(MetadataFileType):
    """
    Playlist files in various playlist formats
    """
    def __init__(self):
        MetadataFileType.__init__(self,'Playlist',
            extensions=['m3u','m3u8','pls']
        )

class Metadata(list):
    """
    Load metadata parsers and match filenames to the parsers
    """
    def __init__(self):
        """
        Register instances of the MetadataFileType classes in the module
        """
        #noinspection PyTypeChecker
        list.__init__(self)
        self.register_metadata(CoverArt())
        self.register_metadata(Playlist())
        self.register_metadata(AbletonAnalysisFile())
        self.register_metadata(Booklet())
        self.register_metadata(OSXSystemFile())
        self.register_metadata(iTunesLP())

    def register_metadata(self,metadata_class):
        """
        Register instance of a MetadataFileType class
        """
        if not isinstance(metadata_class,MetadataFileType):
            raise ValueError('Not a MetadataFileType instance')
        self.append(metadata_class)

    def unregister_metadata(self,metadata_class):
        for cls in self:
            if isinstance(cls,metadata_class):  
                self.remove(cls)
                return
        raise ValueError('MetadataFileType instance was not registered')

    def match(self,path):
        """
        Match path to registered metadata type parsers.
        Returns matching metadata class or None
        """
        for m in self:
            if m.match(path):
                return m
        return None

