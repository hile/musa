
__all__ = ['cli','formats','metadata','tags']

import os,sys,unicodedata

def normalized(path,normalization='NFC'):
    """
    Return given path value as normalized unicode string on OS/X,
    on other platform return the original string as unicode
    """
    if sys.platform != 'darwin':
        return type(path)==unicode and path or unicode(path,'utf-8')
    return unicodedata.normalize(
        normalization, type(path)==unicode and path or unicode(path,'utf-8')
    )

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
        self.__delslice__(0,len(self))
        for path in os.getenv('PATH').split(os.pathsep):
            if not self.paths.count(path):
                self.paths.append(path)
        for path in self.paths:
            if not os.path.isdir(path):
                continue
            for cmd in [os.path.join(path,f) for f in os.listdir(path)]:
                if os.path.isdir(cmd) or not os.access(cmd,os.X_OK):
                    continue
                self.append(cmd)

    def versions(self,name):
        """
        Returns all commands with given name on path, ordered by PATH search
        order.
        """
        if not len(self):
            self.update()
        return filter(lambda x: os.path.basename(x) == name, self)

    def which(self,name):
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

