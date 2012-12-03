"""
Module for transcoding
"""

import sys,os,time,tempfile,threading,subprocess

from musa import MUSA_USER_DIR
from musa.cli import MusaThread,MusaScriptError
from musa.tags import TagError
from musa.tree import Tree,Track,TreeError

class TranscoderError(Exception):
    def __str__(self):
        return self.args[0]

class TranscoderThread(MusaThread):
    """
    Class to transcode one file from Transcoder queue.
    """
    def __init__(self,src,dst,overwrite=False,dry_run=False):
        MusaThread.__init__(self,'musa-transcoder')
        self.src = src
        self.dst = dst
        self.overwrite = overwrite
        self.dry_run = dry_run

    def execute(self,command):
        p = subprocess.Popen(command,stdin=sys.stdin,stdout=sys.stdout,stderr=sys.stderr)
        return p.wait()

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
                    print 'Remove: %s' % self.dst.path
            except OSError,(ecode,emsg):
                raise TranscoderError(
                    'Error removing %s: %s' % (self.dst.path,emsg)
                )

        dst_dir = os.path.dirname(self.dst.path)
        if not os.path.isdir(dst_dir):
            try:
                if not self.dry_run:
                    os.makedirs(dst_dir)
                else:
                    print 'Create Directory: %s' % dst_dir
            except OSError,(ecode,emsg):
                raise TranscoderError(
                    'Error creating directory %s: %s' % (dst_dir,emsg)
                )

        wav = tempfile.NamedTemporaryFile(
            dir=MUSA_USER_DIR, prefix='musa-', suffix='.wav',
        )
        try:
            decoder = self.src.get_decoder_command(wav.name)
            encoder = self.dst.get_encoder_command(wav.name)
        except TreeError,emsg:
            raise TranscoderError(emsg)

        try:
            if not self.dry_run:
                self.status = 'decoding: %s' % ' '.join(decoder)
                self.execute(decoder)
                self.status = 'encoding: %s' % ' '.join(encoder)
                self.execute(encoder)
            else:
                print 'Execute: %s' % ' '.join(decoder)
                print 'Execute: %s' % ' '.join(encoder)
            del(wav)
        except TranscoderError,emsg:
            if wav and os.path.isfile(wav):
                try:
                    del(wav)
                except OSError:
                    pass
            self.status = str(e)
            return

        try:
            self.status = 'tagging'
            if self.src.tags is not None:
                if not self.dry_run:
                    if self.dst.tags is not None:
                        self.dst.tags.update_tags(self.src.tags.as_dict())
                        if self.dst.tags.modified:
                            self.dst.tags.save()
                    else:
                        # Destination does not support tags
                        pass
                else:
                    print 'Copy tags to %s' % self.dst.path
        except TagError,emsg:
            raise TranscoderError(emsg)
        self.status = 'finished'

class MusaTranscoder(list):
    def __init__(self,threads,overwrite=False,dry_run=False):
        self.threads = threads
        self.overwrite = overwrite
        self.dry_run = dry_run

    def enqueue(self,src,dst):
        if not isinstance(src,Track) or not isinstance(dst,Track):
            raise TranscoderError('Trancode arguments must be track object')
        if not os.path.isfile(src.path):
            raise TranscoderError('No such file: %s' % src.path)

        try:
            src_decoder = src.get_decoder_command('/tmp/test.wav')
        except TreeError,emsg:
            raise TranscoderError(emsg)
        try:
            dst_encoder = dst.get_encoder_command('/tmp/test.wav')
        except TreeError,emsg:
            raise TranscoderError(emsg)
        self.append((src,dst))

    def run(self,dry_run=False):
        """
        Transcode enqueued songs to given target directory. The songs are
        transcoded using as many threads as the Transcoder was configured to
        use.
        """
        if len(self)==0:
            return

        while len(self)>0:
            active = threading.active_count()
            if active > self.threads:
                time.sleep(0.5)
                continue
            (src,dst) = self.pop(0)
            t = TranscoderThread(src,dst,self.overwrite,self.dry_run)
            t.start()
        active = threading.active_count()
        while active > 1:
            time.sleep(0.5)
            active = threading.active_count()

