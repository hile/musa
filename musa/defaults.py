"""
Default settings for musa configuration database
"""

# Default settings for empty database
INITIAL_SETTINGS = {
    'threads':  4,
    'default_codec': 'mp3',
}

# Default codec commands and parameters when nothing is configured yet
DEFAULT_CODECS = {

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
    'extensions': ['m4a','aac', 'mp4'],
    'encoders': [
        'neroAacEnc -if FILE -of OUTFILE -br 256000 -2pass',
        'afconvert -b 256000 --soundcheck-generate -f m4af -d aac FILE OUTFILE',
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
        'flac -f --silent --verify --replay-gain --best -o OUTFILE FILE',
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
      'encoders': [],
      'decoders': [
        'cp FILE OUTFILE',
      ],
  },

}
