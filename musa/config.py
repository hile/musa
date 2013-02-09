"""
Musa configuration database
"""

import os,configobj

from musa import MUSA_USER_DIR,MusaError
from musa.log import MusaLogger
from musa.sqlite import SqliteDB,SqliteDBError
from musa.defaults import INITIAL_SETTINGS,DEFAULT_CODECS,LEGACY_SYNC_CONFIG

DEFAULT_CONFIG_PATH = os.path.join(MUSA_USER_DIR,'config.sqlite')

CONFIG_SQL = [
"""
CREATE TABLE IF NOT EXISTS settings (
    id          INTEGER PRIMARY KEY,
    key         TEXT,
    value       TEXT
);
""",
"""
CREATE UNIQUE INDEX IF NOT EXISTS settings_pairs ON settings(key,value);
""",
"""
CREATE TABLE IF NOT EXISTS trees (
    id          INTEGER PRIMARY KEY,
    path        TEXT UNIQUE,
    description TEXT
);
""",
"""
CREATE TABLE IF NOT EXISTS synctargets (
    id          INTEGER PRIMARY KEY,
    name        TEXT UNIQUE,
    type        TEXT,
    src         TEXT,
    dst         TEXT,
    flags       TEXT,
    defaults    BOOLEAN
);
""",
"""
CREATE UNIQUE INDEX IF NOT EXISTS synctargets_pairs ON synctargets(src,dst);
""",
"""
CREATE TABLE IF NOT EXISTS codec (
    id          INTEGER PRIMARY KEY,
    name        TEXT UNIQUE,
    description TEXT
);
""",
"""
CREATE TABLE IF NOT EXISTS codec_extension (
    id          INTEGER PRIMARY KEY,
    codec       INT,
    extension   TEXT UNIQUE,
    FOREIGN KEY (codec) REFERENCES codec(id)
)
""",
"""
CREATE UNIQUE INDEX IF NOT EXISTS codec_extensions ON codec_extension(codec,extension);
""",
"""
CREATE TABLE IF NOT EXISTS decoder (
    id          INTEGER PRIMARY KEY,
    codec       INT,
    command     TEXT,
    FOREIGN KEY (codec) REFERENCES codec(id)
)
""",
"""
CREATE UNIQUE INDEX IF NOT EXISTS decoder_commands ON decoder(codec,command);
""",
"""
CREATE TABLE IF NOT EXISTS encoder (
    id          INTEGER PRIMARY KEY,
    codec       INT,
    command     TEXT,
    FOREIGN KEY (codec) REFERENCES codec(id)
)
""",
"""
CREATE UNIQUE INDEX IF NOT EXISTS encoder_commands ON encoder(codec,command);
""",
]

FIELD_CONVERT_MAP = {
    'threads':  lambda x: int(x)
}

class MusaConfigDB(object):
    __config_instance = None
    def __init__(self,path=None):

        if not MusaConfigDB.__config_instance:
            MusaConfigDB.__config_instance = MusaConfigDB.MusaConfigInstance(path)
        self.__dict__['MusaConfigDB.__config_instance'] = MusaConfigDB.__config_instance

    def __getattr__(self,attr):
        return getattr(self.__config_instance,attr)

    class MusaConfigInstance(SqliteDB):
        def __init__(self,path):
            self.log = MusaLogger('musa').default_stream

            path = path is not None and path or DEFAULT_CONFIG_PATH
            config_dir = os.path.dirname(path)
            if not os.path.isdir(config_dir):
                try:
                    os.makedirs(config_dir)
                except OSError(ecode,emsg):
                    raise MusaError('Error creating directory: %s' % config_dir)

            SqliteDB.__init__(self,path,CONFIG_SQL,foreign_keys=True)

            for key,value in INITIAL_SETTINGS.items():
                if self.get(key) is None:
                    self.set(key,value)

            self.codecs = CodecConfiguration(config=self)
            self.sync = SyncConfiguration(config=self)

        def get(self,key):
            c = self.cursor
            c.execute("""SELECT value FROM settings WHERE key=?""",(key,))
            res = c.fetchone()
            if res is not None:
                return self.__format_item__(key,res[0])
            return None

        def set(self,key,value):
            key = unicode(key)
            value = unicode(value)
            c = self.cursor
            c.execute("""DELETE FROM settings WHERE key=?""", (key,))
            c.execute("""INSERT INTO settings (key,value) VALUES (?,?)""",(key,value,))
            self.commit()

        def __getitem__(self,key):
            value = self.get(key)
            if value is not None:
                return value
            raise KeyError('No such value in settings: %s' % key)

        def __setitem__(self,key,value):
            self.set(key,value)

        def __format_item__(self,key,value):
            if key in FIELD_CONVERT_MAP.keys():
                try:
                    value = FIELD_CONVERT_MAP[key](value)
                except ValueError:
                    raise MusaError('Invalid data in configuration for field %s' % key)
            return value

        def has_key(self,key):
            c = self.cursor
            c.execute("""SELECT key FROM settings where key=?""",(key,))
            return c.fetchone() is not None

        def keys(self):
            c = self.cursor
            c.execute("""SELECT key FROM settings""")
            return [r[0] for r in c.fetchall()]

        def items(self):
            c = self.cursor
            c.execute("""SELECT key,value FROM settings""")
            items = []
            for res in c.fetchall():
                items.append( (res[0],self.__format_item__(res[0],res[1])) )
            return items

        def values(self):
            return [v for k,v in self.items()]

        def delete_tree(self,path,description=''):
            c = self.cursor
            c.execute("""DELETE FROM trees WHERE path=?""", (path,))
            self.commit()

        def add_tree(self,path,description=''):
            c = self.cursor
            c.execute("""DELETE FROM trees WHERE path=?""", (path,))
            c.execute("""INSERT INTO trees (path,description) VALUES (?,?)""",(path,description,))
            self.commit()

        def get_trees(self):
            c = self.cursor
            c.execute("""SELECT path from trees""")
            return [r[0] for r in c.fetchall()]

class SyncConfiguration(dict):
    def __init__(self,config):
        self.log = MusaLogger('musa').default_stream
        self.config = config

        c = self.config.cursor
        c.execute("""SELECT * from synctargets""")
        for target in [self.config.as_dict(c,r) for r in c.fetchall()]:
            self[target['name']] = target

        self.import_legacy_config()

    @property
    def threads(self):
        return self.config.get('threads')

    @property
    def default_targets(self):
        return [k for k in self.keys() if self[k]['defaults']]

    def create_target(self,name,synctype,src,dst,flags,defaults=False):
        c = self.config.cursor
        c.execute("""INSERT INTO synctargets (name,type,src,dst,flags,defaults) VALUES (?,?,?,?,?,?)""",
            (name,synctype,src,dst,flags,defaults,)
        )
        self.config.commit()
        c.execute("""SELECT * FROM synctargets WHERE name=?""",(name,))
        entry = self.config.as_dict(c,c.fetchone())
        self[entry['name']] = entry

    def import_legacy_config(self,cleanup=False):
        path = LEGACY_SYNC_CONFIG
        if not os.path.isfile(path):
            return
        config = configobj.ConfigObj(infile=path,interpolation=False,list_values=False)
        for name,target in config.items():
            if name=='options' or name in self.keys():
                continue
            target['synctype'] = target.pop('type')
            entry = self.config.sync.create_target(name,**target)

        try:
            os.unlink(path)
        except OSError,(ecode,emsg):
            pass

class CodecConfiguration(dict):
    def __init__(self,config):
        self.log = MusaLogger('musa').default_stream
        self.config = config
        self.load()

    def load(self):
        c = self.config.cursor
        c.execute("""SELECT * FROM codec""")
        for codec in [self.config.as_dict(c,r) for r in c.fetchall()]:
            self.update(codec)

        for codec_id in [c['id'] for c in self.items()]:
            c.execute("""SELECT extension FROM codec_extension WHERE codec=?""",(codec_id,))
            self['extensions'] = [r[0] for r in c.fetchall()]

            c.execute("""SELECT command FROM decoder WHERE codec=?""",(codec_id,))
            self['decoders'] = [r[0] for r in c.fetchall()]

            c.execute("""SELECT command FROM encoder WHERE codec=?""",(codec_id,))
            self['encoders'] = [r[0] for r in c.fetchall()]

        for name,settings in DEFAULT_CODECS.items():
            if name in self.keys():
                continue

            self[name] = settings

    def update_codec_description(self,name,description):
        c = self.config.cursor
        c.execute("""SELECT id FROM codec WHERE name=?""",(name,))
        res = c.fetchone()
        if res:
            c.execute("""UPDATE codec SET description=? WHERE name=?""",(description,name,))
        else:
            c.execute("""INSERT INTO codec SET (name,description) VALUES (?,?)""",(name,description,))
        self.config.commit()

    def keys(self):
        return sorted(dict.keys(self))

    def items(self):
        return [(k,self[k]) for k in self.keys()]

    def values(self):
        return [self[k] for k in self.keys()]
