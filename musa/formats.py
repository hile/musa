#!/usr/bin/env python
"""
Guessing of supported file formats
"""

import os
from musa import normalized,CommandPathCache
from musa.metadata import Metadata

#
# Default codec commands and parameters 
CODECS = {

  'mp3': {
    'description': 'MPEG-1 or MPEG-2 Audio Layer III',
    'extensions':   ['mp3'],
    'encoders': [
        'lame --quiet -b 320 --vbr-new -ms --replaygain-accurate FILE OUTFILE',
    ],
    'decoders': [
        'lame --quiet --decode FILE OUTFILE',
    ],
  },

  'aac': {
    'description': 'Advanced Audio Coding',
    'extensions': ['aac', 'm4a', 'mp4'],
    'encoders': [
        'neroAacEnc -if FILE -of OUTFILE -br 256000 -2pass',
        'afconvert -b 256000 -v -f m4af -d aac FILE OUTFILE',
    ],
    'decoders': [
        'neroAacDec -if OUTFILE -of FILE',
        'faad -q -o OUTFILE FILE -b1',
    ],
  },

  'vorbis': {
    'description': 'Ogg Vorbis',
    'extensions': ['vorbis','ogg'], 
    'encoders': [
        'oggenc --quiet -q 7 -o OUTFILE FILE',
    ],
    'decoders': [
        'oggdec --quiet -o OUTFILE FILE',
    ],
  },

  'flac': {
    'description': 'Free Lossless Audio Codec',
    'extensions': ['flac'], 
    'encoders': [
        'flac -f --silent --verify --replay-gain QUALITY -o OUTFILE FILE',
    ],
    'decoders': [
        'flac -f --silent --decode -o OUTFILE FILE',
    ],
  },

  'wavpack': {
    'description': 'WavPack Lossless Audio Codec',
    'extensions': ['wv','wavpack'], 
    'encoders': [ 'wavpack -yhx FILE -o OUTFILE', ],
    'decoders': [ 'wvunpack -yq FILE -o OUTFILE', ],
  },

  'caf': {
    'description': 'CoreAudio Format audio',
    'extensions':   ['caf'],
    'encoders': [
        'afconvert -f caff -d LEI16 FILE OUTFILE',
    ],
    'decoders': [
        'afconvert -f WAVE -d LEI16 FILE OUTFILE',
    ],
  },

  'aif': {
      'description': 'AIFF audio',
      'extensions':   ['aif','aiff'],
      'encoders': [ 
        'afconvert -f AIFF -d BEI16 FILE OUTFILE',
      ],
      'decoders': [
        'afconvert -f WAVE -d LEI16 FILE OUTFILE',
      ],
      },

  # TODO - Raw audio, what should be decoder/encoder commands?
  'wav': {
      'description': 'RIFF Wave Audio',
      'extensions':   ['wav'],
      'encoders': [], 'decoders': [],
  },

}

TAG_PARSERS = {
    'aac':      'musa.tags.formats.aac.aac',
    'mp3':      'musa.tags.formats.mp3.mp3',
    'flac':     'musa.tags.formats.flac.flac',
    'vorbis':   'musa.tags.formats.vorbis.vorbis',
}

PATH_CACHE = CommandPathCache()
PATH_CACHE.update()

def filter_available_command_list(commands):
    available = []
    for command in commands:
        try:
            executable = command.split(' ',1)[0]
        except IndexError:
            executable = command
            pass
        if PATH_CACHE.which(executable) is None:
            continue
        available.append(command)
    return available 

def match_codec(path):
    ext = os.path.splitext(path)[1][1:]
    if ext in CODECS.keys():
        return ext
    for codec,details in CODECS.items():
        if not 'extensions' in details:
            continue
        if ext in details['extensions']:
            return codec
    return None

def match_metadata(path):
    metadata = Metadata()
    m = metadata.match(path)
    if m:
        return m 
    return False

class MusaFileFormat(object):
    def __init__(self,path):
        self.path = normalized(path)
        self.codec = None
        self.description = None
        self.is_metadata = False
        
        self.codec = match_codec(path)
        if self.codec is not None:
            if not 'description' in CODECS[self.codec]:
                raise TypeError('CODECS missing description for %s' % self.codec)
            self.description = CODECS[self.codec]['description'].lower()
        else:
            m = match_metadata(path)
            if m:   
                self.is_metadata = True
                self.description = m.description.lower()
            elif os.path.isdir(path):
                self.description = 'unknown directory'
            else:
                self.description = 'unknown file format'

    def __repr__(self):
        return '%s %s' % (self.codec,self.path)

    def get_tag_parser(self):
        if self.codec is None or self.codec not in TAG_PARSERS.keys():
            return None
        try:
            classpath = TAG_PARSERS[self.codec]
            module_path = '.'.join(classpath.split('.')[:-1])
            class_name = classpath.split('.')[-1]
            m = __import__(module_path,globals(),fromlist=[class_name])
            return getattr(m,class_name)
        except KeyError,emsg:
            #logger.debug('Error loading tag parser for %s' % self.path)
            return None 

    def get_available_encoders(self):
        if self.codec is None:
            return []
        config = CODECS[self.codec]
        if not 'encoders' in config:
            return []
        return filter_available_command_list(config['encoders'])

    def get_available_decoders(self):
        if self.codec is None:
            return []
        config = CODECS[self.codec]
        if not 'decoders' in config:
            return []
        return filter_available_command_list(config['decoders'])

if __name__ == '__main__':
    import sys
    for f in sys.argv[1:]:
        f=MusaFileFormat(f)

