# coding=utf-8
"""Tree synchronization

Parsing of syncing options

"""

import os
import shutil
import time

from subprocess import Popen, PIPE

from musa.defaults import MUSA_USER_DIR
from musa.cli import ScriptThread, MusaThreadManager
from soundforest.config import ConfigDB
from soundforest.log import SoundforestLogger
from soundforest.tree import Tree, Track, TreeError

SYNC_LOG = os.path.join(MUSA_USER_DIR, 'sync.log')

RSYNC_DELETE_FLAGS = (
    '--del',
    '--delete',
    '--delete-before',
    '--delete-during',
    '--delete-after',
    '--delete-delay',
    '--delete-excluded'
)
DEFAULT_DELETE_FLAG = '--delete-before'

class SyncError(Exception):
    pass


def ntfs_rename(path):
    REPLACE_MAP = {
        '|': '-',
        '>': '-',
        '<': '-',
        '"': '',
        ':': ' - ',
        '?': '',
        '!': '',
        '*': '',
    }
    for c, r in REPLACE_MAP.items():
        path = path.replace(c, r)

    # Silly system does not allow components ending with .
    path = os.sep.join(x.rstrip('. ') for x in path.split(os.sep))
    return path

RENAME_CALLBACKS = {
    'ntfs': ntfs_rename,
}

class SyncThread(ScriptThread):
    def __init__(self, manager, index, src, dst, delete=False):
        ScriptThread.__init__(self, 'sync')
        self.manager = manager
        self.index = index
        self.delete = delete

        if isinstance(src, Tree):
            self.src_tree = src
            self.src = src.path

        elif isinstance(src, basestring):
            self.src_tree = Tree(src)
            self.src = os.path.expandvars(src).rstrip(os.sep)

        else:
            raise SyncError('Src is not string or Tree object: %s' % src)

        if isinstance(dst, Tree):
            self.dst_tree = dst
            self.dst = dst.path

        elif isinstance(dst, basestring):
            self.dst_tree = Tree(dst)
            self.dst = os.path.expandvars(dst).rstrip(os.sep)

        else:
            raise SyncError('Dst is not string or Tree object: %s' % dst)

    def run(self):
        raise NotImplementedError('Must be implemented in inheriting class')

class FilesystemSyncThread(SyncThread):
    def __init__(self, manager, index, src, dst, delete=False, rename=None):
        SyncThread.__init__(self, manager, index, src, dst, delete)

        if rename is not None:
            try:
                rename = RENAME_CALLBACKS[rename]
            except KeyError:
                raise SyncError('Unknown rename callback: %s' % rename)

        self.rename = rename

    def copy_track(self, src, dst):
        try:
            shutil.copyfile(src, dst)

        except IOError, (ecode, emsg):
            raise SyncError('Error writing to %s: %s' % (dst, emsg))

        except OSError, (ecode, emsg):
            raise SyncError('Error writing to %s: %s' % (dst, emsg))

    def run(self):
        if not os.path.isdir(self.src_tree.path):
            raise SyncError('Source not available while syncing: %s' % self.src_tree.path)

        if not os.path.isdir(self.dst_tree.path):
            raise SyncError('Destination not available while syncing: %s' % self.dst_tree.path)

        src = self.src_tree
        dst = self.dst_tree
        i=0

        for album in src.as_albums():
            dst_album_path = os.path.join(dst.path, src.relative_path(album.path))
            if self.rename is not None:
                dst_album_path = self.rename(dst_album_path)

            if not os.path.isdir(dst_album_path):
                try:
                    self.log.info('Create directory: %s' % dst_album_path)
                    os.makedirs(dst_album_path)

                except OSError, (ecode, emsg):
                    self.log.info('Error creating directory %s: %s' % (dst_album_path, emsg))
                    continue

            for track in album:
                i+=1
                dst_track_path = os.path.join(dst.path, track.relative_path)

                if self.rename:
                    dst_track_path = self.rename(dst_track_path)
                dst_track = Track(os.path.join(dst_track_path))

                modified = False
                if not os.path.isfile(dst_track.path):
                    self.log.info('%6d new: %s' % (i, dst_track.path))
                    modified = True

                elif track.size != dst_track.size:
                    self.log.info('%6d modified: %s' % (i, dst_track.path))
                    modified = True

                if modified:
                    try:
                        self.copy_track(track.path, dst_track.path)

                    except SyncError, emsg:
                        print emsg
                        continue

class RsyncThread(SyncThread):
    def __init__(self, manager, index, src, dst, flags, delete=False):
        SyncThread.__init__(self, manager, index, src, dst, delete)
        if isinstance(flags, basestring):
            flags = flags.split()

        if delete and not RSYNC_DELETE_FLAGS.intersection(set(flags)):
            flags.insert(0, DEFAULT_DELETE_FLAG)

        self.flags = flags

    def run(self):
        command = ['rsync', '-av'] + self.flags + ['%s/' % self.src, '%s/' % self.dst]
        print 'running ', ' '.join(command)

        try:
            self.log.info('Running: %s' % ' '.join(command))

            p = Popen(command, stdin=PIPE, stdout=PIPE, stderr=PIPE)
            rval = None
            while rval is None:
                while True:
                    l = p.stdout.readline()
                    if l == '': break
                    self.log.info(l.rstrip())
                time.sleep(0.2)
                rval = p.poll()

            if rval != 0:
                self.log.info('Error running command %s: %s' % (self, p.stderr.read()))

        except KeyboardInterrupt:
            self.log.debug('Rsync interrupted')
            raise KeyboardInterrupt

        self.log.info('Finished: %s' % ' '.join(command))

class SyncManager(MusaThreadManager):
    def __init__(self, threads=None, delete=False, debug=False):
        MusaThreadManager.__init__(self, 'sync', threads)
        self.delete = delete
        self.debug = debug

        if not debug:
            self.log = SoundforestLogger('sync').register_file_handler('sync', MUSA_USER_DIR)
            SoundforestLogger('sync').set_level('INFO')

        else:
            self.log = SoundforestLogger().default_stream

    def parse_target(self, name):
        try:
            target = self.db.sync[name]

        except KeyError:
            return None

        if not 'src' in target:
            raise SyncError('Target missing source')

        if not 'dst' in target:
            raise SyncError('Target missing destination')

        return target

    @property
    def rename_callbacks(self):
        return RENAME_CALLBACKS

    def get_entry_handler(self, index, config):
        sync_type = config.pop('type', None)
        if sync_type=='rsync':
            return RsyncThread(manager=self, index=index, **config)

        elif sync_type=='directory':
            if 'flags' in config:
                del config['flags']
            return FilesystemSyncThread(manager=self, index=index, **config)

        else:
            raise SyncError('BUG: invalid sync type in thread config')

    def enqueue(self, config):
        if not isinstance(config, dict):
            raise SyncError('Enqueue requires a dictionary')

        sync_type = config.get('type', None)
        if sync_type not in ['rsync', 'directory']:
            raise SyncError('Unknown sync type in config: %s' % sync_type)

        if 'delete' not in config:
            config['delete'] = self.delete

        for k in ('id', 'name', 'defaults'):
            if k in config:
                config.pop(k)

        self.append(config)

