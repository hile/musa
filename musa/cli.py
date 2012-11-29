
"""
Command line utilities for musa
"""

import sys,os,time,argparse,signal,logging,socket
import logging.handlers
import threading

from setproctitle import setproctitle
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

DEFAULT_LOGFORMAT = '%(levelname)s %(message)s'
DEFAULT_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
DEFAULT_LOGFILEFORMAT = \
    '%(asctime)s %(module)s.%(funcName)s %(message)s'
DEFAULT_LOGSIZE_LIMIT = 2**20
DEFAULT_LOG_BACKUPS = 10

class MusaScriptLogger(object):
    """
    Class for common script logging tasks. Implemented as singleton to prevent
    errors in duplicate handler initialization.
    """
    __instances = {}
    def __init__(self,program=None):
        if program is None:
            program = 'python'
        if not MusaScriptLogger.__instances.has_key(program):
            MusaScriptLogger.__instances[program] = \
                MusaScriptLogger.ScriptLoggerInstance(program)
        self.__dict__['_MusaScriptLogger__instances'] = MusaScriptLogger.__instances
        self.__dict__['program'] = program

    class ScriptLoggerInstance(dict):
        """
        Singleton implementation of logging configuration for one program
        """
        def __init__(self,program):
            dict.__init__(self)
            self.program = program
            self.loglevel = logging.Logger.root.level

        def __getattr__(self,attr):
            if attr == 'level':
                return self.loglevel
            raise AttributeError(
                'No such ScriptLoggerInstance attribute: %s' % attr
            )

        def __setattr__(self,attr,value):
            if attr in ['level','loglevel']:
                for logger in self.values():
                    logger.setLevel(value)
                self.__dict__['loglevel'] = value
            else:
                object.__setattr__(self,attr,value)

    def __getattr__(self,attr):
        return getattr(self.__instances[self.program],attr)

    def __setattr__(self,attr,value):
        setattr(self.__instances[self.program],attr,value)

    def __getitem__(self,item):
        return self.__instances[self.program][item]

    def __setitem__(self,item,value):
        self.__instances[self.program][item] = value

    def stream_handler(self,name,logformat=None,timeformat=None):
        """
        Register a common log stream handler
        """
        if logformat is None:
            logformat = DEFAULT_LOGFORMAT
        if timeformat is None:
            timeformat = DEFAULT_TIME_FORMAT

        for logging_manager in logging.Logger.manager.loggerDict.values():
            if hasattr(l,'name') and l.name==name:
                return

        logger = logging.getLogger(name)
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(logformat,timeformat))
        logger.addHandler(handler)
        self[name] = logger

    def file_handler(self,name,directory,
                     logformat=None,
                     maxBytes=DEFAULT_LOGSIZE_LIMIT,
                     backupCount=DEFAULT_LOG_BACKUPS):
        """
        Register a common log file handler for rotating file based logs
        """
        if logformat is None:
            logformat = DEFAULT_LOGFILEFORMAT

        if name in [l.name for l in logging.Logger.manager.loggerDict.values()]:
            return
        if not os.path.isdir(directory):
            try:
                os.makedirs(directory)
            except OSError:
                raise MusaScriptError('Error creating directory: %s' % directory)

        logger = logging.getLogger(name)
        logfile = os.path.join(directory,'%s.log' % name)
        handler = logging.handlers.RotatingFileHandler(
            filename=logfile,
            mode='a+',
            maxBytes=maxBytes,
            backupCount=backupCount
        )
        handler.setFormatter(logging.Formatter(logformat,self.timeformat))
        logger.addHandler(handler)
        logger.setLevel(self.loglevel)
        self[name] = logger

class MusaThread(threading.Thread):
    """
    Common script thread base class
    """
    def __init__(self,name):
        threading.Thread.__init__(self)
        self.status = 'not running'
        self.setDaemon(True)
        self.setName(name)
        self.logger = MusaScriptLogger()
        self.log = logging.getLogger('modules')

class MusaScript(object):
    """
    Common musa CLI tool setup class
    """
    def __init__(self,program=None,description=None,epilog=None):
        self.name = os.path.basename(sys.argv[0])
        setproctitle('%s %s' % (self.name,' '.join(sys.argv[1:])))
        signal.signal(signal.SIGINT, self.SIGINT)

        reload(sys)
        sys.setdefaultencoding('utf-8')

        if program is None:
            program = self.name

        self.logger = MusaScriptLogger(program=program)
        self.log = logging.getLogger('console')

        self.parser = argparse.ArgumentParser(
            prog=program,
            description=description,
            epilog=epilog,
            add_help=False
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

    def add_argument(self,*args,**kwargs):
        """
        Shortcut to add argument to main argumentparser instance
        """
        self.parser.add_argument(*args,**kwargs)

    def parse_args(self):
        """
        Call parse_args for parser and check for default logging flags
        """
        args = self.parser.parse_args()
        if hasattr(args,'debug') and getattr(args,'debug'):
            self.logger.level = logging.DEBUG
        elif hasattr(args,'verbose') and getattr(args,'verbose'):
            self.logger.level = logging.INFO
        return args

    def read_stdin(self):
        """
        Read text data from stdin, return as lines
        """
        buffer = []
        while True:
            line = sys.stdin.readline()
            if line=='': break
            buffer.append(line[:-1])
        return buffer

class MusaCommand(object):
    """
    Parent class for musa cli subcommands
    """
    def __init__(self,script,name,helptext):
        if name in script.commands:
            raise MusaScriptError('Duplicate sub command name: %s' % name)
        self.name = name
        self.script = script
        self.parser = script.command_parsers.add_parser(name,help=helptext)
        script.commands[name] = self

    def parse_args(self,args):
        """
        Common argument parsing
        """
        if args.command != self.name:
            raise MusaScriptError('Called wrong sub command class')

        dirs,tracks = [],[]
        for path in args.paths:  
            if os.path.isdir(path):
                dirs.append(Tree(path))
            elif os.path.isfile(path):
                tracks.append(Track(path))
            else:
                self.script.exit(1,'No such file or directory: %s' % path)

        tracks_found = False
        for d in dirs:
            if len(d):
                tracks_found = True
                break

        if not tracks_found and not len(tracks):
            self.script.exit(1,'No music files detected')

        return dirs,tracks 

