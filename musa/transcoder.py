# coding=utf-8
"""Transcoding support

Module for transcoding between file formats

"""

import sys
import os
import shutil
import time
import tempfile

from musa.defaults import MUSA_CACHE_DIR
from musa.cli import ScriptThread, MusaThreadManager
from soundforest.tags import TagError
from soundforest.tree import Tree, Album, Track, TreeError


class TranscoderError(Exception):
    """Exceptions raised by transcoder threads"""

    def __str__(self):
        return self.args[0]


class TranscoderThread(ScriptThread):
    """
    Class to transcode one file from Transcoder queue.
    """

    def __init__(self, index, src, dst, overwrite=False, dry_run=False):
        super(TranscoderThread, self).__init__('convert')
        self.index = index
        self.src = src
        self.dst = dst
        self.overwrite = overwrite
        self.dry_run = dry_run

        if not os.path.isdir(MUSA_CACHE_DIR):
            try:
                os.makedirs(MUSA_CACHE_DIR)
            except OSError, (ecode, emsg):
                raise TranscoderError('Error creating directory {0}: {1}'.format(MUSA_CACHE_DIR, emsg))

    def error(self, message):
        print message
        sys.exit(1)

    def run(self):
        """
        Run the thread, calling source_song.decode() to create a temporary
        wav file and dst_song.encode() to encode this wav file to target file.
        """
        self.status = 'initializing'

        if self.overwrite and os.path.isfile(self.dst.path):
            try:
                if not self.dry_run:
                    os.unlink(self.dst.path)
                else:
                    self.log.debug('remove: {0}'.format(self.dst.path))
            except OSError, (ecode, emsg):
                self.error('Error removing {0}: {1}'.format(self.dst.path, emsg))

        dst_dir = os.path.dirname(self.dst.path)
        if not os.path.isdir(dst_dir):
            try:
                if not self.dry_run:
                    os.makedirs(dst_dir)
            except OSError, (ecode, emsg):
                if os.path.isdir(dst_dir):
                    # Other thread created directory before us, forget it
                    pass
                else:
                    self.error('Error creating directory {0}: {1}'.format(dst_dir, emsg))

        wav = tempfile.NamedTemporaryFile(
            dir=MUSA_CACHE_DIR, prefix='musa-', suffix='.wav'
        )
        src_tmp = tempfile.NamedTemporaryFile(
            dir=MUSA_CACHE_DIR, prefix='musa-', suffix='.{0}'.format(self.src.extension)
        )
        src = Track(src_tmp.name)
        dst_tmp = tempfile.NamedTemporaryFile(
            dir=MUSA_CACHE_DIR, prefix='musa-', suffix='.{0}'.format(self.dst.extension)
        )
        src = Track(src_tmp.name)
        dst = Track(dst_tmp.name)
        if not self.dry_run:
            open(src.path, 'wb').write(open(self.src.path, 'rb').read())

        try:
            decoder = src.get_decoder_command(wav.name)
            encoder = dst.get_encoder_command(wav.name)
        except TreeError, emsg:
            self.error(emsg)


        try:
            if not self.dry_run:
                self.status = 'transcoding'
                self.log.debug('decoding: {0} {1}'.format(self.index, self.src.path))
                self.execute(decoder)
                self.log.debug('encoding: {0} {1}'.format(self.index, self.dst.path))
                self.execute(encoder)
                shutil.copyfile(dst.path, self.dst.path)
            else:
                self.log.debug('decoder: {0}'.format(' '.join(decoder)))
                self.log.debug('encoder: {0}'.format(' '.join(encoder)))
                self.log.debug('target file: {0}'.format(self.dst.path))
            del(wav)

        except TranscoderError, emsg:
            if wav and os.path.isfile(wav):
                try:
                    del(wav)
                except OSError:
                    pass
            self.status = str(e)
            self.error('ERROR transcoding: {0}'.format(emsg))

        if not self.dry_run and not os.path.isfile(self.dst.path):
            self.error('File was not successfully transcoded: {0}'.format(self.dst.path))

        if not self.dry_run:
            try:
                self.status = 'tagging'
                if self.src.tags is not None:
                    self.log.debug('tagging:  {0} {1}'.format(self.index, self.dst.path))
                    if not self.dry_run:
                        if self.dst.tags is not None:
                            if self.dst.tags.update_tags(self.src.tags.as_dict()):
                                self.dst.tags.save()
                        else:
                            # Destination does not support tags
                            pass
            except TagError, emsg:
                self.error(emsg)

        self.status = 'finished'


class MusaTranscoder(MusaThreadManager):
    def __init__(self, threads, overwrite=False, dry_run=False):
        super(MusaTranscoder, self).__init__('convert', int(threads))
        self.overwrite = overwrite
        self.dry_run = dry_run

    def enqueue(self, src, dst):
        if not isinstance(src, Track) or not isinstance(dst, Track):
            raise TranscoderError('Trancode arguments must be track object')

        if not os.path.isfile(src.path):
            raise TranscoderError('No such file: {0}'.format(src.path))

        try:
            src_decoder = src.get_decoder_command('/tmp/test.wav')
        except TreeError, emsg:
            raise TranscoderError(str(emsg))

        try:
            dst_encoder = dst.get_encoder_command('/tmp/test.wav')
        except TreeError, emsg:
            raise TranscoderError(str(emsg))

        self.log.debug('enqueue: {0} -> {1}'.format(src.path, dst.path))
        self.append((src, dst))

    def get_entry_handler(self, index, entry):
        src, dst = entry
        return TranscoderThread(index, src, dst, self.overwrite, self.dry_run)

    def run(self):
        self.log.debug('Transcoding {0} files with {1:d} threads'.format(len(self), self.threads))
        MusaThreadManager.run(self)

