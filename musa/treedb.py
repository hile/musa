"""
Database classes to store music track information
"""

import os,logging,hashlib

from datetime import datetime,timedelta
from pytz import UTC

from musa.log import MusaLogger
from musa.tree import Tree,Track,TreeError
from musa.formats import match_codec,match_metadata
from musa.sqlite import SqliteDB,SqliteDBError

TREE_SQL = [
"""
CREATE TABLE IF NOT EXISTS album (
    id          INTEGER PRIMARY KEY,
    path        TEXT UNIQUE,
    atime       DATETIME,
    ctime       DATETIME,
    mtime       DATETIME,
    checksum    TEXT
)
""",
"""
CREATE TABLE IF NOT EXISTS track (
    id          INTEGER PRIMARY KEY,
    album       INTEGER,
    filename    TEXT,
    extension   TEXT,
    size        INTEGER,
    atime       DATETIME,
    ctime       DATETIME,
    mtime       DATETIME,
    checksum    TEXT,
    FOREIGN KEY(album) REFERENCES album(id) ON DELETE CASCADE
);
""",
"""CREATE UNIQUE INDEX IF NOT EXISTS track_paths ON track (album,filename,extension)""",
"""CREATE UNIQUE INDEX IF NOT EXISTS track_mtimes ON track (album,filename,extension,mtime)""",
"""
CREATE TABLE IF NOT EXISTS tag (
    id          INTEGER PRIMARY KEY,
    track       INTEGER,
    tag         TEXT,
    value       TEXT,
    base64      BOOLEAN DEFAULT 0,
    FOREIGN KEY(track) REFERENCES track(id) ON DELETE CASCADE
);
""",
"""
CREATE UNIQUE INDEX IF NOT EXISTS file_tags ON tag(track,tag,value);
""",
]

class TreeDB(object):

    def __init__(self,tree):
        """
        Sqlite database of files in a music tree, stored to root directory
        of the tree as .musa.sqlite file.
        """

        self.log =  MusaLogger('musa').default_stream
        self.info = {'id': None, 'ctime': None, 'mtime': None }

        if isinstance(tree,basestring):
            tree = Tree(tree)

        self.tree = tree
        self.db = SqliteDB(self.tree.db_file,queries=TREE_SQL,foreign_keys=True)
        self.path = self.tree.path

    class DBAlbum(list):
        def __init__(self,tree,album):
            self.log =  MusaLogger('musa').default_stream
            self.tree = tree
            self.album = album
            self.path = album.relative_path()
            self.modified = False

            st = os.stat(self.album.path)
            c = self.tree.db.cursor
            c.execute("""SELECT id,mtime FROM album WHERE path=?""",(self.path,))
            res = c.fetchone()
            if res is None:
                c.execute(
                    """INSERT INTO album (path,atime,ctime,mtime) VALUES (?,?,?,?)""",
                    (self.path, st.st_atime, st.st_ctime, st.st_mtime, )
                )
                self.modified = True
                self.tree.db.commit()
            elif res[1]!=st.st_mtime:
                self.modified = True


            c.execute("""SELECT id,atime,ctime,mtime FROM album WHERE path=?""",(self.path,))
            for k,v in self.tree.db.as_dict(c,c.fetchone()).items():
                setattr(self,k,v)

        def update_stats(self):
            c = self.tree.db.cursor
            st = os.stat(self.album.path)
            c.execute(
                    """UPDATE album SET atime=?,ctime=?,mtime=? WHERE path=?""",
                    (st.st_atime, st.st_ctime, st.st_mtime, self.path, )
            )
            self.tree.db.commit()

    class DBTrack(dict):
        def __init__(self,tree,album,filename):
            self.log =  MusaLogger('musa').default_stream
            self.tree = tree
            self.album = album
            self.filename = filename
            self.modified = False

            st = os.stat(self.path)
            c = self.tree.db.cursor
            c.execute(
                """SELECT id,size,mtime FROM track WHERE album=? and filename=?""",
                (self.album.id,self.filename,)
            )
            res = c.fetchone()
            if res is None:
                extension = os.path.splitext(filename)[1][1:]
                c.execute(
                    """INSERT INTO track (album,filename,extension,size,atime,mtime,ctime) VALUES (?,?,?,?,?,?,?)""",
                    (self.album.id,self.filename,extension,st.st_size,st.st_atime,st.st_mtime,st.st_ctime,)
                )
                self.modified = True
            elif res[0]!=st.st_size or res[2]!=st.st_mtime:
                c.execute(
                    """UPDATE track SET size=?,atime=?,mtime=?,ctime=? WHERE id=?""",
                    (st.st_size, st.st_atime, st.st_mtime, st.st_ctime, res[0], )
                )
                self.modified = True
            self.tree.db.commit()

            c.execute("""SELECT id,atime,ctime,mtime,checksum FROM track WHERE album=? AND filename=?""",
                (self.album.id,self.filename,))
            for k,v in self.tree.db.as_dict(c,c.fetchone()).items():
                setattr(self,k,v)

        @property
        def path(self):
            return os.path.join(self.tree.path,self.album.path,self.filename)

        def update_checksum(self):
            shasum = hashlib.sha1()
            shasum.update(open(self.path,'r').read())
            checksum = shasum.hexdigest()
            if self.checksum == checksum:
                return None
            c = self.tree.db.cursor
            c.execute("""UPDATE track SET checksum=? WHERE id=?""", (checksum,self.id,) )
            self.tree.db.commit()
            return checksum

        def update_tags(self):
            tags = Track(self.path).tags
            if not tags:
                return
            c = self.tree.db.cursor

            modified = False
            c.execute("""SELECT id,tag FROM tag WHERE track=?""", (self.id,) )
            res = c.fetchall()
            for r in res:
                if r[1] in tags.keys():
                    continue
                c.execute("""DELETE FROM tag WHERE track=? AND tag=?""", (self.id,r[0],))
            if modified:
                self.tree.db.commit()

            modified = False
            for tag,value in tags.items():
                c.execute(
                    """SELECT id,value FROM tag WHERE track=? AND tag=?""",
                    (self.id,tag,)
                )
                res = c.fetchone()
                if res is None:
                    c.execute(
                        """INSERT INTO tag (track,tag,value) VALUES (?,?,?)""",
                        ( self.id, tag, value, )
                    )
                    modified = True
                else:
                    if res[1]==value:
                        continue
                    c.execute(
                        """UPDATE tag SET value=? WHERE track=? AND tag=?""",
                        ( value, track, tag, )
                    )
                    modified = True

            if modified:
                self.tree.db.commit()

    def update(self,tags=True,checksum=True):

        if not self.tree.has_been_iterated:
            self.tree.load()

        for album in self.tree.as_albums():
            album.load()

            if not album.files:
                continue

            db_album = self.DBAlbum(self,album)
            if not db_album.modified:
                continue

            self.log.debug('Album: %s' % db_album.path)
            for directory,filename in album.files:
                self.log.debug('Track: %s' % os.path.join(directory,filename))
                db_track = self.DBTrack(self,db_album,filename)

                if checksum:
                    if db_track.update_checksum() and tags:
                        db_track.update_tags()

                elif tags and db_track.modified:
                    db_track.update_tags()

                db_album.append(db_track)

            # Only update album timestamps after tracks are done
            db_album.update_stats()

    def summary(self,fields=['tags','tracks','albums']):

        if not isinstance(fields,set):
            fields = set(fields)
        summary = {}
        c = self.db.cursor

        for field in fields:
            if field=='tags':
                c.execute(
                    """SELECT count(id) FROM tag where track in (SELECT DISTINCT id FROM track)""",
                )
                summary['tags'] = c.fetchone()[0]

            if field=='tracks':
                c.execute("""SELECT count(id) FROM track""")
                summary['tracks'] = c.fetchone()[0]

            if field=='albums':
                c.execute("""select count(id) from album""")
                summary['albums'] = c.fetchone()[0]

        return summary
