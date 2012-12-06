
"""
Command line utilities for musa
"""

import sys,os,time,argparse,signal,socket
import threading,tempfile

from subprocess import Popen,PIPE

from setproctitle import setproctitle
from musa.log import MusaLogger
from musa.prefixes import TreePrefixes
from musa.formats import match_metadata
from musa.tree import Tree,Track,TreeError

def xterm_title(value,max_length=74,bypass_term_check=False):
    """
    Set title in xterm titlebar to given value, clip the title text to
    max_length characters.
    """
    TERM=os.getenv('TERM')
    TERM_TITLE_SUPPORTED = [ 'xterm','xterm-debian']
    if not bypass_term_check and TERM not in TERM_TITLE_SUPPORTED:
        return
    sys.stdout.write('\033]2;'+value[:max_length]+'',)
    sys.stdout.flush()

class MusaScriptError(Exception):
    """
    Exceptions raised by running scripts
    """
    def __str__(self):
        return self.args[0]

class MusaThread(threading.Thread):
    """
    Common script thread base class
    """
    def __init__(self,name):
        threading.Thread.__init__(self)
        self.log = MusaLogger(name).default_stream
        self.status = 'not running'
        self.setDaemon(True)
        self.setName(name)

class MusaTagsEditor(MusaThread):
    def __init__(self,tmpfile):
        MusaThread.__init__(self,'musa-edit')
        self.tmpfile = tmpfile
        self.log = MusaLogger('tags').default_stream

    def run(self):
        self.status = 'edit'

        editor = os.getenv('EDITOR').split()
        if editor is None:
            editor = ['open','-w']
            #editor = ['vi']
        cmd = editor + [self.tmpfile]
        p = Popen(cmd,stdin=sys.stdin,stdout=sys.stdout,stderr=sys.stderr)
        p.wait()
        self.status = 'finished'
        return

class MusaScript(object):
    """
    Common musa CLI tool setup class
    """
    def __init__(self,name=None,description=None,epilog=None):
        self.name = os.path.basename(sys.argv[0])
        setproctitle('%s %s' % (self.name,' '.join(sys.argv[1:])))
        signal.signal(signal.SIGINT, self.SIGINT)

        reload(sys)
        sys.setdefaultencoding('utf-8')

        if name is None:
            name = self.name

        self.logger = MusaLogger(name)
        self.log = self.logger.default_stream

        self.parser = argparse.ArgumentParser(
            prog=name,
            description=description,
            epilog=epilog,
            add_help=False,
            conflict_handler='resolve',
        )

        self.commands = {}
        self.command_parsers = self.parser.add_subparsers(
            dest='command', help='additional help',
            title='subcommmands', description='valid subcommands'
        )

    def SIGINT(self,signum,frame):
        """
        Parse SIGINT signal by quitting the program cleanly with exit code 1
        """
        for t in filter(lambda t: t.name!='MainThread', threading.enumerate()):
            t.join()
        self.exit(1)

    def wait(self,poll_interval=1):
        """
        Wait for running threads to finish.
        Poll interval is time to wait between checks for threads
        """
        while True:
            active = filter(lambda t: t.name!='MainThread', threading.enumerate())
            if not len(active):
                break
            self.log.debug('Waiting for %d threads' % len(active))
            time.sleep(poll_interval)

    def exit(self,value=0,message=None):
        """
        Exit the script with given exit value.
        If message is not None, it is printed on screen.
        """
        if message is not None:
            print message
        while True:
            active = filter(lambda t: t.name!='MainThread', threading.enumerate())
            if not len(active):
                break
            time.sleep(1)
        sys.exit(value)

    def register_subcommand(self,command,name,help):
        if name in self.commands:
            raise MusaScriptError('Duplicate sub command name: %s' % name)
        self.commands[name] = command
        return self.command_parsers.add_parser(name,help=help)

    def add_argument(self,*args,**kwargs):
        """
        Shortcut to add argument to main argumentparser instance
        """
        self.parser.add_argument(*args,**kwargs)

    def edit_tags(self,tags):
        """
        Dump, open and load back a dictionary with EDITOR
        """
        if not isinstance(tags,dict):
            raise MusaScriptError('Argument not a dictionary')
        tmp = tempfile.NamedTemporaryFile(
            dir=os.getenv('HOME'), prefix='.musa-', suffix='.txt'
        )
        fd = open(tmp.name,'w')
        for k in sorted(tags.keys()):
            fd.write('%s=%s\n' % (k,tags[k]))
        fd.close()

        editor = MusaTagsEditor(tmp.name)
        editor.start()
        self.wait()

        new_tags = {}
        for l in [l.strip() for l in open(tmp.name,'r').readlines()]:
            try:
                if l.strip()=='' or l[:1]=='#':
                    continue
                k,v = [x.strip() for x in l.split('=',1)]
                if k in new_tags.keys():
                    raise MusaScriptError('Duplicate tag in data')
                new_tags[k] = v
            except ValueError,emsg:
                raise MusaScriptError('Error parsing new tags from file: %s' % emsg)
        return new_tags

    def parse_args(self):
        """
        Call parse_args for parser and check for default logging flags
        """
        args = self.parser.parse_args()
        if hasattr(args,'debug') and getattr(args,'debug'):
            self.logger.set_level('DEBUG')
        return args

class MusaCommand(object):
    """
    Parent class for musa cli subcommands
    """
    def __init__(self,script,name,helptext,mode_flags=[],debug=True):
        self.name = name
        self.script = script

        self.logger = MusaLogger(name)
        self.log = self.logger.default_stream

        if not isinstance(mode_flags,list):
            raise MusaScriptError('Mode flags must be a list')
        self.mode_flags = mode_flags
        self.selected_mode_flags = []

        self.parser = script.register_subcommand(self,name,help=helptext)
        if debug:
            self.parser.add_argument('--debug',action='store_true',help='Debug messages')

    def get_tags(self,track):
        if isinstance(track,Track):
            try:
                return track.tags
            except TreeError,emsg:
                pass
        return None

    def process_tracks(self,trees,tracks,command,**kwargs):
        """
        Execute command for all tracks in trees or track list
        """
        for tree in trees:
            for track in tree:
                command(track=track,**kwargs)
        for track in tracks:
            command(track=track,**kwargs)

    def parse_args(self,args):
        """
        Common argument parsing
        """
        if args.command != self.name:
            raise MusaScriptError('Called wrong sub command class')

        if hasattr(args,'debug') and getattr(args,'debug'):
            self.logger.set_level('DEBUG')

        self.prefixes = TreePrefixes()

        dirs,tracks,metadata = [],[],[]
        for path in args.paths:
            if os.path.isdir(path):
                dirs.append(Tree(path))
            else:
                try:
                    tracks.append(Track(path))
                except TreeError:
                    match = match_metadata(path)
                    if match is not None:
                        metadata.append(match)

        tracks_found = False
        for d in dirs:
            if len(d):
                tracks_found = True
                break

        if not tracks_found and not len(tracks) and not len(metadata):
            return [],[],[]

        self.selected_mode_flags = filter(lambda x:
            getattr(args,x) not in [None,False,[]],
            self.mode_flags
        )

        return dirs,tracks,metadata

