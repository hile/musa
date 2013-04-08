# coding=utf-8
"""Musa configuration database

Musa configuration database, implementing the database classes in
musa.models for cli scripts as script.cli.db.

"""

import os
import configobj

from musa import MusaError
from musa.log import MusaLogger
from musa.models import MusaDB, Setting, SyncTarget, Codec, Extension, Decoder, Encoder, DBTreeType
from musa.defaults import INITIAL_SETTINGS, DEFAULT_CODECS, DEFAULT_TREE_TYPES, LEGACY_SYNC_CONFIG

FIELD_CONVERT_MAP = {
    'threads': lambda x: int(x)
}


class MusaConfigDB(object):


    """MusaConfigDB

    Musa database settings API.

    """

    __db_instance = None
    def __init__(self,path=None):

        if not MusaConfigDB.__db_instance:
            MusaConfigDB.__db_instance = MusaConfigDB.MusaConfigInstance(path)
        self.__dict__['MusaConfigDB.__db_instance'] = MusaConfigDB.__db_instance

    def __getattr__(self, attr):
        return getattr(self.__db_instance, attr)

    class MusaConfigInstance(MusaDB):

        def __init__(self, path):
            self.log = MusaLogger('musa').default_stream
            MusaDB.__init__(self, path=path)

            for key, value in INITIAL_SETTINGS.items():
                if self.get(key) is None:
                    self.log.debug('Setting default for %s is %s' % (key,value))
                    self.set(key, value)

            treetypes = self.session.query(DBTreeType).all()
            if not treetypes:
                treetypes = []
                for name,description in DEFAULT_TREE_TYPES.items():
                    treetypes.append(DBTreeType(name=name,description=description))
                self.add(treetypes)
                self.commit()

            self.codecs = CodecConfiguration(db=self)
            self.sync = SyncConfiguration(db=self)
            self.sync.import_legacy_config()

        def get(self, key):
            entry = self.session.query(Setting).filter(Setting.key==key).first()
            return entry is not None and entry.value or None

        def set(self, key, value):
            existing = self.session.query(Setting).filter(Setting.key==key).first()
            if existing:
                self.session.delete(existing)
            self.session.add(Setting(key=key,value=value))
            self.session.commit()

        def __getitem__(self, key):
            value = self.get(key)
            if value is not None:
                return value
            raise KeyError('No such value in settings: %s' % key)

        def __setitem__(self, key, value):
            self.set(key, value)

        def __format_item__(self, key, value):
            if key in FIELD_CONVERT_MAP.keys():
                try:
                    value = FIELD_CONVERT_MAP[key](value)
                except ValueError:
                    raise MusaError('Invalid data in configuration for field %s' % key)
            return value

        def has_key(self, key):
            return self.get(key) is not None

        def keys(self):
            return [s.key for s in self.session.query(Setting).all()]

        def items(self):
            return [(s.key,s.value) for s in self.session.query(Setting).all()]

        def values(self):
            return [s.value for s in self.session.query(Setting).all()]

class SyncConfiguration(dict):

    """SyncConfiguration

    Directory synchronization target configuration API

    """

    def __init__(self, db):
        self.log = MusaLogger('musa').default_stream
        self.db = db

        for target in self.db.sync_targets:
            self[target.name] = target.as_dict()

    @property
    def threads(self):
        return self.db.get('threads')

    @property
    def default_targets(self):
        return [k for k in self.keys() if self[k]['defaults']]

    def create_sync_target(self,name,synctype,src,dst,flags=None,defaults=False):
        self[name] = self.db.register_sync_target(name,synctype,src,dst,flags,defaults)

    def import_legacy_config(self,cleanup=False):
        path = LEGACY_SYNC_CONFIG
        if not os.path.isfile(path):
            return

        config = configobj.ConfigObj(infile=path, interpolation=False, list_values=False)
        for name, target in config.items():
            if name == 'options' or name in self.keys():
                continue
            target['synctype'] = target.pop('type')
            if 'rsync_flags' in target.keys():
                target['flags'] = target.pop('rsync_flags')

            existing = filter(lambda x: x['src'] == target['src'] and x['dst'] == target['dst'], self.values())
            if existing:
                continue

            entry = self.db.sync.create_sync_target(name,**target)

        try:
            os.unlink(path)
        except OSError, (ecode, emsg):
            pass


class CodecConfiguration(dict):

    """CodecConfiguration

    Audio codec decoder/encoder commands configuration API

    """

    def __init__(self, db):
        self.log = MusaLogger('musa').default_stream
        self.db = db
        self.load()

    def load(self):
        for codec in self.db.registered_codecs:
            self[str(codec.name)] = codec

        for name, settings in DEFAULT_CODECS.items():
            if name  in self.keys():
                continue
            self.log.debug('Import default codec: %s' % name)
            codec = self.db.register_codec(name,**settings)
            self[str(codec.name)] = codec

    def extensions(self,codec):
        if codec in self.keys():
            return [codec] + [e.extension for e in self[codec].extensions]
        return []

    def keys(self):
        return sorted(dict.keys(self))

    def items(self):
        return [(k, self[k]) for k in self.keys()]

    def values(self):
        return [self[k] for k in self.keys()]
