# coding=utf-8
"""CLI utilities

Command line utilities for musa

"""

import sys
import os
import time
import logging
import argparse
import tempfile
import signal
import socket
import threading
import subprocess

from soundforest.cli import Script, ScriptCommand, ScriptThread, ScriptThreadManager, ScriptError
from soundforest.prefixes import TreePrefixes
from soundforest.formats import match_metadata, match_codec
from soundforest.tree import Tree, Track, TreeError


class MusaThreadManager(ScriptThreadManager):
    def __init__(self, name, threads=None):
        super(MusaThreadManager, self).__init__(name, threads)

    def enqueue(self, item):
        self.log.debug('enqueue: {0}'.format(src.path))
        self.append((src, dst))

    def run(self):
        if len(self)==0:
            return

        total = len(self)
        while len(self)>0:
            active = threading.active_count()
            if active > self.threads:
                time.sleep(0.5)
                continue

            index = '{0:d}/{1:d}'.format(total-len(self)+1, total)
            t = self.get_entry_handler(index, self.pop(0))
            t.start()

        active = threading.active_count()
        while active > 1:
            time.sleep(0.5)
            active = threading.active_count()


class MusaTagsEditor(ScriptThread):
    def __init__(self, tmpfile):
        super(MusaTagsEditor, self).__init__('musa-edit')
        self.tmpfile = tmpfile

    def run(self):
        self.status = 'edit'

        editor = os.getenv('EDITOR').split()
        if editor is None:
            editor = ['vi']

        cmd = editor + [self.tmpfile]
        p = subprocess.Popen(cmd, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr)
        p.wait()
        self.status = 'finished'


class MusaScript(Script):
    """
    Musa CLI tool setup class
    """

    def edit_tags(self, tags):
        """
        Dump, open and load back a dictionary with EDITOR
        """
        if not isinstance(tags, dict):
            raise ScriptError('Argument not a dictionary')

        tmp = tempfile.NamedTemporaryFile(
            dir=os.getenv('HOME'),
            prefix='.musa-tags',
            suffix='.txt'
        )

        fd = open(tmp.name, 'w')
        for k in sorted(tags.keys()):
            for v in tags[k]:
                fd.write('{0}={1}\n'.format(k, v))
        fd.close()

        editor = MusaTagsEditor(tmp.name)
        editor.start()
        self.wait()

        new_tags = {}
        for l in [l.strip() for l in open(tmp.name, 'r').readlines()]:
            try:
                if l.strip()=='' or l[:1]=='#':
                    continue

                k, v = [x.strip() for x in l.split('=', 1)]
                if k in new_tags.keys():
                    new_tags[k].append(v)
                else:
                    new_tags[k] = [v]

            except ValueError, emsg:
                raise ScriptError('Error parsing new tags from file: {0}'.format(emsg))

        return new_tags

class MusaScriptCommand(ScriptCommand):
    """
    Parent class for musa cli subcommands
    """

    def get_tags(self, track):
        if isinstance(track, Track):
            try:
                return track.tags

            except TreeError, emsg:
                self.log.debug('Error parsing tags from {0}: {1}'.format(track.path, emsg))
                return None

        return None

    def get_codec(self, codec):
        return match_codec(codec)

    def process_tracks(self, trees, tracks, command, **kwargs):
        """
        Execute command for all tracks in trees or track list
        """
        for tree in trees:
            for track in tree:
                command(track=track, **kwargs)

        for track in tracks:
            command(track=track, **kwargs)

    def read_input_to_dict(self, fd):
        tags = {}

        with fd as input:
            for line in [l.rstrip() for l in input]:
                tag, value = None,  None
                for sep in ('=', ' ', '\t'):
                    try:
                        tag, value = [x.strip() for x in line.split(sep, 1)]
                    except ValueError:
                        pass

                if tag is None or value is None:
                    raise ScriptError('Invalid tag input line: {0}'.format(line))
                tags[tag] = unicode(value)

        return tags

    def run(self, args, skip_targets=False):
        """
        Common argument parsing
        """
        args = super(MusaScriptCommand, self).parse_args(args)

        self.prefixes = TreePrefixes()

        if skip_targets:
            return [], [], []

        trees, tracks, metadata = [], [], []
        for path in args.paths:
            if os.path.isdir(path):
                trees.append(Tree(path))

            else:
                try:
                    tracks.append(Track(path))
                except TreeError:
                    match = match_metadata(path)
                    if match is not None:
                        metadata.append(match)

        tracks_found = False
        for d in trees:
            if not len(d):
                continue
            tracks_found = True
            break

        if not tracks_found and not len(tracks) and not len(metadata):
            return [], [], []

        return trees, tracks, metadata

