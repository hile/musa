# coding=utf-8
"""Musa default settings

Default settings for musa configuration database and commands.

"""

import sys
import os

if sys.platform=='darwin':
    MUSA_USER_DIR = os.path.expanduser('~/Library/Application Support/Musa')
    MUSA_CACHE_DIR = os.path.expanduser('~/Library/Caches/Musa')
else:
    MUSA_USER_DIR = os.path.expanduser('~/.config/musa')
    MUSA_CACHE_DIR = os.path.expanduser('~/.cache/musa')

# Default settings for empty database
INITIAL_SETTINGS = {
    'threads':  4,
    'default_codec': 'mp3',
}
