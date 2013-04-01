"""
Musa configuration database
"""

import os
import configobj

from musa import MusaError
from musa.log import MusaLogger
from musa.models import MusaDB, Setting, SyncTarget, Codec, Extension, Decoder, Encoder, TreeType, Tree, Track
from musa.defaults import INITIAL_SETTINGS, DEFAULT_CODECS, DEFAULT_TREE_TYPES, LEGACY_SYNC_CONFIG

FIELD_CONVERT_MAP = {
    'threads': lambda x: int(x)
}


class MusaConfigDB(object):


    """MusaConfigDB

    Musa configuration settings API.

    """

    __config_instance = None
    def __init__(self,path=None):

        if not MusaConfigDB.__config_instance:
            MusaConfigDB.__config_instance = MusaConfigDB.MusaConfigInstance(path)
        self.__dict__['MusaConfigDB.__config_instance'] = MusaConfigDB.__config_instance

    def __getattr__(self, attr):
        return getattr(self.__config_instance, attr)

    class MusaConfigInstance(MusaDB):

        def __init__(self, path):
            self.log = MusaLogger('musa').default_stream
            MusaDB.__init__(self, path=path)

            for key, value in INITIAL_SETTINGS.items():
                if self.get(key) is None:
                    self.log.debug('Setting default for %s is %s' % (key,value))
                    self.set(key, value)

            treetypes = self.session.query(TreeType).all()
            if not treetypes:
                treetypes = []
                for name,description in DEFAULT_TREE_TYPES.items():
                    treetypes.append(TreeType(name=name,description=description))
                self.add(treetypes)
                self.commit()

            self.codecs = CodecConfiguration(config=self)
            self.sync = SyncConfiguration(config=self)
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

    def __init__(self, config):
        self.log = MusaLogger('musa').default_stream
        self.config = config

        for target in self.config.query(SyncTarget):
            self[target.name] = self.config.as_dict(target)

    @property
    def threads(self):
        return self.config.get('threads')

    @property
    def default_targets(self):
        return [k for k in self.keys() if self[k]['defaults']]

    def create_target(self,name,synctype,src,dst,flags=None,defaults=False):
        target = SyncTarget(name=name,type=synctype,src=src,dst=dst,flags=flags,defaults=defaults)
        self.config.save(target)
        self[name] = self.config.as_dict(target)

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

            entry = self.config.sync.create_target(name,**target)

        try:
            os.unlink(path)
        except OSError, (ecode, emsg):
            pass


class CodecConfiguration(dict):

    """CodecConfiguration

    Audio codec decoder/encoder commands configuration API

    """

    def __init__(self, config):
        self.log = MusaLogger('musa').default_stream
        self.config = config
        self.load()

    def register_codec(self,name,extensions,description='',decoders=[],encoders=[]):
        """
        Register codec with given parameters
        """
        codec = Codec(name=name,description=description)
        extensions = [Extension(codec=codec,extension=e) for e in extensions]
        decoders = [Decoder(codec=codec,priority=i,command=d) for i,d in enumerate(decoders)]
        encoders = [Encoder(codec=codec,priority=i,command=e) for i,e in enumerate(encoders)]
        self.config.add([codec]+extensions+decoders+encoders)
        return codec

    def load(self):
        for codec in self.config.query(Codec).all():
            self[codec.name] = codec

        for name, settings in DEFAULT_CODECS.items():
            if name  in self.keys():
                continue
            self.log.debug('Import default codec: %s' % name)
            codec = self.register_codec(name,**settings)
            self[codec.name] = codec

    def add_decoder(self,codec,command,priority=None):
        codec = self.config.query(Codec).filter(Codec.name==name)

        if priority is None:
            # TODO - implement inserting with given priority, pushing
            # earlier instance priorities around.
            priority = len(codec['decoders'])+1

        decoder = Decoder(codec=codec,priority=priority,command=command)

        self.session.add(decoder)
        self.session.commmit()

    def remove_decoder(self,codec,command,priority=None):
        codec = self.config.query(Codec).filter(Codec.name==name)

        if priority is not None:
            decoders = self.config.query(Decoder).filter(
                Decoder.codec==codec,
                Decoder.priority==priority,
                Decoder.command==command
            )
        else:
            decoders = self.config.query(Decoder).filter(
                Decoder.codec==codec,
                Decoder.command==command
            )
        for d in decoders:
            self.session.delete(d)
        self.session.commit()

    def update_codec_description(self, name, description):
        codec = self.config.query(Codec).filter(Codec.name==name)
        codec.description = description
        self.config.commit()

    def extensions(self,codec):
        if codec in self.keys():
            return [e.extension for e in self[codec].extensions]
        return []

    def keys(self):
        return sorted(dict.keys(self))

    def items(self):
        return [(k, self[k]) for k in self.keys()]

    def values(self):
        return [self[k] for k in self.keys()]
