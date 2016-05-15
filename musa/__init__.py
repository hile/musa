# coding=utf-8
"""Musa audio library management tools

Audio file processing libraries

"""
__version__ = '4.0.2'

import os
import sys
import unicodedata

from musa.defaults import MUSA_USER_DIR

class MusaError(Exception):
    pass

def normalized(path, normalization='NFC'):
    """
    Return given path value as normalized unicode string on OS/X,
    on other platform return the original string as unicode
    """
    if sys.platform != 'darwin':
        if not isinstance(path, unicode):
            return unicode(path, 'utf-8')
    if not isinstance(path, unicode):
        path = unicode(path, 'utf-8')
    return unicodedata.normalize(normalization, path)


class CommandPathCache(list):

    """
    Class to represent commands on user's search path.
    """
    def __init__(self):
        list.__init__(self)
        self.paths = None
        self.update()

    def update(self):
        """
        Updates the commands available on user's PATH
        """
        self.paths = []
        self.__delslice__(0, len(self))
        for path in os.getenv('PATH').split(os.pathsep):
            if not self.paths.count(path):
                self.paths.append(path)
        for path in self.paths:
            if not os.path.isdir(path):
                continue
            for cmd in [os.path.join(path, f) for f in os.listdir(path)]:
                if os.path.isdir(cmd) or not os.access(cmd, os.X_OK):
                    continue
                self.append(cmd)

    def versions(self, name):
        """
        Returns all commands with given name on path, ordered by PATH search
        order.
        """
        if not len(self):
            self.update()
        return filter(lambda x: os.path.basename(x) == name, self)

    def which(self, name):
        """
        Return first matching path to command given with name, or None if
        command is not on path
        """
        if not len(self):
            self.update()
        try:
            return filter(lambda x: os.path.basename(x) == name, self)[0]
        except IndexError:
            return None

if not os.path.isdir(MUSA_USER_DIR):
    try:
        os.makedirs(MUSA_USER_DIR)
    except OSError, (ecode, emsg):
        raise MusaError('Error creating directory {0}: {1}'.format(dst_dir, emsg))
