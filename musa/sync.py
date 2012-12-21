"""
Parsing of syncing options
"""

import os,configobj

from musa import MUSA_USER_DIR,MusaError
from musa.cli import MusaThread,MusaThreadManager
from musa.tree import Tree,Track,TreeError

USER_SYNC_CONFIG = os.path.join(MUSA_USER_DIR,'sync.conf')

class SyncError(Exception):
    def __str__(self):
        return self.args[0]

class SyncThread(MusaThread):
    def __init__(self,index,command):
        MusaThread.__init__(self,'sync')
        self.index = index
        self.command = command

    def run(self):
        self.log.debug('Syncing: %s' % self.command)

class SyncManager(MusaThreadManager):
    def __init__(self,threads=1):
        MusaThreadManager.__init__(self,'sync',threads)
        self.config = SyncConfig()
        #for k,v in self.config.items(): print k,v

    def parse_target(self,name):
        try:
            target = self.config[name]
        except KeyError:
            return None
        if not 'src' in target:
            raise SyncError('Target missing source')
        if not 'dst' in target:
            raise SyncError('Target missing destination')
        return target

    def get_entry_handler(self,index,target):
        return SyncThread(index,target)

    def enqueue(self,name):
        self.append(name)

class SyncConfig(dict):
    def __init__(self,path=None):
        self.path = path is not None or USER_SYNC_CONFIG
        self['options'] = {
            'default': None,
            'threads': 1,
        }
        config = configobj.ConfigObj(infile=self.path)
        self.update(dict(config.items()))


