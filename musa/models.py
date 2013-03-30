#!/usr/bin/env python
"""Musa Models

SQLAlchemy models for musa configuration and music tree databases

"""

import os

from sqlite3 import Connection as SQLite3Connection
from sqlalchemy import create_engine, event, Column, ForeignKey, Integer, Boolean, Date
from sqlalchemy.exc import IntegrityError
from sqlalchemy.types import TypeDecorator, Unicode
from sqlalchemy.orm import sessionmaker, relationship, backref
from sqlalchemy.ext.declarative import declarative_base

from musa import MUSA_USER_DIR, MusaError

DEFAULT_DATABASE = os.path.join(MUSA_USER_DIR, 'musa.sqlite')

Base = declarative_base()

class SafeUnicode(TypeDecorator):
    """Safely coerce Python bytestrings to Unicode
    before passing off to the database."""

    impl = Unicode

    def process_bind_param(self, value, dialect):
        if isinstance(value, str):
            value = value.decode('utf-8')
        return value

class Setting(Base):

    """Musa internal application preferences
    """

    __tablename__ = 'musa_settings'

    id = Column(Integer, primary_key=True)
    key = Column(SafeUnicode)
    value = Column(SafeUnicode)


class SyncTarget(Base):
    __tablename__ = 'musa_sync_targets'

    id = Column(Integer, primary_key=True)
    name = Column(SafeUnicode, unique=True)
    type = Column(SafeUnicode)
    src = Column(SafeUnicode)
    dst = Column(SafeUnicode)
    flags = Column(SafeUnicode)
    defaults = Column(Boolean)

class Codec(Base):

    """Audio format codecs
    """

    __tablename__ = 'codecs'

    id = Column(Integer, primary_key=True)
    name = Column(SafeUnicode)
    description = Column(SafeUnicode)

    def __repr__(self):
        return self.name


class Extension(Base):

    """Filename extensions associated with audio format codecs
    """

    __tablename__ = 'extensions'

    id = Column(Integer, primary_key=True)
    extension = Column(SafeUnicode)
    codec_id = Column(Integer, ForeignKey('codecs.id'), nullable=False)
    codec = relationship("Codec", single_parent=False,
        backref=backref('extensions', order_by=extension, cascade="all, delete, delete-orphan")
    )

    def __repr__(self):
        return self.extension


class Decoder(Base):

    """Audio format codec decoders
    """

    __tablename__ = 'decoders'

    id = Column(Integer, primary_key=True)
    priority = Column(Integer)
    command = Column(SafeUnicode)
    codec_id = Column(Integer, ForeignKey('codecs.id'), nullable=False)
    codec = relationship("Codec", single_parent=False,
        backref=backref('decoders', order_by=priority, cascade="all, delete, delete-orphan")
        )

    def __repr__(self):
        return '%s decoder: %s' % (self.codec.name, self.command)


class Encoder(Base):

    """Audio format codec encoders
    """

    __tablename__ = 'encoders'

    id = Column(Integer, primary_key=True)
    priority = Column(Integer)
    command = Column(SafeUnicode)
    codec_id = Column(Integer, ForeignKey('codecs.id'), nullable=False)
    codec = relationship("Codec", single_parent=False,
        backref=backref('encoders', order_by=priority, cascade="all, delete, delete-orphan")
        )

    def __repr__(self):
        return '%s encoder: %s' % (self.codec.name, self.command)


class PlaylistSource(Base):

    """Playlist parent folders
    """

    __tablename__ = 'playlist_sources'

    id = Column(Integer, primary_key=True)
    name = Column(SafeUnicode)
    path = Column(SafeUnicode)

    def __repr__(self):
        return '%s: %s' % (self.name, self.path)


class Playlist(Base):

    """Playlist of audio tracks
    """

    __tablename__ = 'playlists'

    id = Column(Integer, primary_key=True)

    updated = Column(Date)
    folder = Column(SafeUnicode)
    name = Column(SafeUnicode)
    description = Column(SafeUnicode)

    parent_id = Column(Integer, ForeignKey('playlist_sources.id'), nullable=False)
    parent = relationship("PlaylistSource", single_parent=False,
        backref=backref('playlists', order_by=[folder, name], cascade="all, delete, delete-orphan")
    )

    def __repr__(self):
        return '%s: %d tracks' % (os.sep.join([self.folder, self.name]), len(self.tracks))


class PlaylistTrack(Base):

    """Audio track in a playlist
    """

    __tablename__ = 'playlist_tracks'

    id = Column(Integer, primary_key=True)

    position = Column(Integer, unique=True)
    path = Column(SafeUnicode)

    playlist_id = Column(Integer, ForeignKey('playlists.id'), nullable=False)
    playlist = relationship("Playlist", single_parent=False,
        backref=backref('tracks', order_by=position, cascade="all, delete, delete-orphan")
    )

    def __repr__(self):
        return '%d %s' % (self.position, self.path)


class TreeType(Base):

    """Audio file tree types (music, samples, loops etc.)
    """

    __tablename__ = 'treetypes'

    id = Column(Integer, primary_key=True)
    name = Column(SafeUnicode)
    description = Column(SafeUnicode)

    def __repr__(self):
        return self.name


class Tree(Base):

    """Audio file tree
    """

    __tablename__ = 'trees'

    id = Column(Integer, primary_key=True)
    path = Column(SafeUnicode,unique=True)
    description = Column(SafeUnicode)

    type_id = Column(Integer, ForeignKey('treetypes.id'), nullable=True)
    type = relationship("TreeType", single_parent=True,
        backref=backref('trees', order_by=path, cascade="all, delete, delete-orphan")
    )

    def __repr__(self):
        return self.path

    def update(self,session,tree):
        added,updated,deleted = 0,0,0

        existing_paths = [track.path for track in self.tracks]
        for track in tree:
            if track.path not in existing_paths:
                db_track = Track(
                    tree=self,
                    directory=track.directory,
                    filename=track.filename,
                    extension=track.extension,
                    mtime=track.mtime,
                    deleted=False,
                )
                db_track.update_tags(session,track.tags)
                added +=1

            else:
                db_track = session.query(Track).filter(Track.directory==track.path.directory,Track.filename==track.path.filename).first()
                if db_track:
                    if track.mtime != db_track.mtime:
                        db_track.update_tags(session,track.tags)
                        updated += 1

            session.commit()

        for track in self.tracks:
            if not track.exists:
                session.delete(track)
                deleted += 1

            session.commit()

        return added,updated,deleted

    def match(self,match):
        print 'Matching %s: %s' % (self,match)
        return []

class Track(Base):

    """Audio file. Optionally associated with a audio file tree
    """

    __tablename__ = 'tracks'

    id = Column(Integer, primary_key=True)

    directory = Column(SafeUnicode)
    filename = Column(SafeUnicode)
    extension = Column(SafeUnicode)
    checksum = Column(SafeUnicode)
    mtime = Column(Integer)
    deleted = Column(Boolean)

    tree_id = Column(Integer, ForeignKey('trees.id'), nullable=True)
    tree = relationship("Tree", single_parent=False,
        backref=backref('tracks', order_by=[directory, filename], cascade="all, delete, delete-orphan")
    )

    def __repr__(self):
        return os.sep.join([self.directory, self.filename])

    @property
    def path(self):
        return os.path.join(self.directory,self.filename)

    @property
    def exists(self):
        return os.path.isfile(self.path)

    def update_tags(self,session,tags):
        for tag in session.query(Tag).filter(Tag.track==self):
            session.delete(tag)

        for tag,value in tags.items():
            session.add(Tag(track=self,tag=tag,value=value))

class Tag(Base):

    """Tags for an audio file
    """

    __tablename__ = 'tags'

    id = Column(Integer, primary_key=True)
    tag = Column(SafeUnicode)
    value = Column(SafeUnicode)
    base64_encoded = Column(Boolean)

    track_id = Column(Integer, ForeignKey('tracks.id'), nullable=False)
    track = relationship("Track", single_parent=False,
        backref=backref('tags', order_by=tag, cascade="all, delete, delete-orphan")
    )

    def __repr__(self):
        return '%s=%s' % (self.tag, self.value)


class MusaDB(object):
    def __init__(self,path=None,engine=None,debug=False):
        if engine is None:
            if path is None:
                path = DEFAULT_DATABASE

            config_dir = os.path.dirname(path)
            if not os.path.isdir(config_dir):
                try:
                    os.makedirs(config_dir)
                except OSError, (ecode, emsg):
                    raise MusaError('Error creating directory: %s' % config_dir)

            engine = create_engine('sqlite:///%s' % path, encoding='utf-8', echo=debug)

        event.listen(engine, 'connect', self._fk_pragma_on_connect)
        Base.metadata.create_all(engine)

        session_instance = sessionmaker(bind=engine)
        self.session = session_instance()

    def _fk_pragma_on_connect(self, connection, record):
        if isinstance(connection, SQLite3Connection):
            cursor = connection.cursor()
            cursor.execute('pragma foreign_keys=ON')
            cursor.close()

    def query(self,*args,**kwargs):
        return self.session.query(*args,**kwargs)

    def commit(self):
        return self.session.commit()

    def as_dict(self,result):
        if not hasattr(result,'__table__'):
            raise ValueError('Not a sqlalchemy ORM result')
        return dict((k.name,getattr(result,k.name)) for k in result.__table__.columns)

    def add(self,items):
        if isinstance(items,list):
            self.session.add_all(items)
        else:
            self.session.add(items)
        self.session.commit()

    @property
    def trees(self):
        return self.session.query(Tree).all()

    def register_tree(self,path,description=''):
        if isinstance(path,str):
            path = unicode(path,'utf-8')
        existing = self.session.query(Tree).filter(Tree.path==path)
        if not existing:
            raise MusaError('Tree was already registered: %s' % path)

        try:
            self.session.add(Tree(path=path,description=description))
            self.session.commit()
        except IntegrityError:
            raise MusaError('Tree was already registered: %s' % path)

    def unregister_tree(self,path,description=''):
        existing = self.session.query(Tree).filter(Tree.path==path).first()
        if not existing:
            raise MusaError('Tree was not registered: %s' % path)

        self.session.delete(existing)
        self.session.commit()

    def get_tree(self,path):
        tree = self.session.query(Tree).filter(Tree.path==path).first()
        return tree
