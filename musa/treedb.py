"""
Database classes to store music track information in sqlite files.
"""

import os,logging,hashlib

from datetime import datetime,timedelta
from pytz import UTC

from musa.log import MusaLogger
from musa.formats import match_codec,match_metadata

class TreeDB(SqliteDB):
    """
    Sqlite database of files in a music tree, stored to root directory
    of the tree as .musa.sqlite file.

    Please note the database:
    - contains ONLY relative paths to the root of the tree
    - does NOT contain any data not available from filesystem
    - may be removed at any moment
    """


    class DBAlbum(list):
        """
        Internal object to map one Album object to database tables
        """
        def __init__(self,treedb,album):
            self.log =  MusaLogger('musa').default_stream
            self.treedb = treedb
            self.album = album
            self.path = album.relative_path()
            self.modified = False

            st = os.stat(self.album.path)
            c = self.treedb.cursor
            c.execute("""SELECT id,mtime FROM album WHERE path=?""",(self.path,))
            res = c.fetchone()
            if res is None:
                c.execute(
                    """INSERT INTO album (path,atime,ctime,mtime) VALUES (?,?,?,?)""",
                    (self.path, st.st_atime, st.st_ctime, st.st_mtime, )
                )
                self.modified = True
                self.treedb.commit()
            elif res[1]!=st.st_mtime:
                self.modified = True

            c.execute("""SELECT id,atime,ctime,mtime FROM album WHERE path=?""",(self.path,))
            for k,v in self.treedb.as_dict(c,c.fetchone()).items():
                setattr(self,k,v)

        def update_stats(self):
            c = self.treedb.cursor
            st = os.stat(self.album.path)
            c.execute(
                """UPDATE album SET atime=?,ctime=?,mtime=? WHERE path=?""",
                (st.st_atime, st.st_ctime, st.st_mtime, self.path, )
            )
            self.treedb.commit()

    class DBTrack(dict):
        """
        Internal object to map one Track object to database tables
        """
        def __init__(self,treedb,album,filename):
            self.log =  MusaLogger('musa').default_stream
            self.treedb = treedb
            self.album = album
            self.filename = filename
            self.modified = False

            st = os.stat(self.path)
            c = self.treedb.cursor
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
            self.treedb.commit()

            c.execute(
                """SELECT id,atime,ctime,mtime,checksum FROM track WHERE album=? AND filename=?""",
                (self.album.id,self.filename,)
            )
            for k,v in self.treedb.as_dict(c,c.fetchone()).items():
                setattr(self,k,v)

        @property
        def path(self):
            return os.path.join(self.tree.path,self.album.path,self.filename)

        def update_checksum(self):
            """
            Update SHA1 checksum of the file to database
            """
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
            """
            Update metadata tags for file to database
            """
            tags = Track(self.path).tags
            if not tags:
                return
            c = self.treedb.cursor

            modified = False
            c.execute("""SELECT id,tag FROM tag WHERE track=?""", (self.id,) )
            res = c.fetchall()
            for r in res:
                if r[1] in tags.keys():
                    continue
                c.execute("""DELETE FROM tag WHERE track=? AND tag=?""", (self.id,r[0],))
            if modified:
                self.treedb.commit()

            modified = False
            for tag,value in tags.items():
                c.execute("""SELECT id,value FROM tag WHERE track=? AND tag=?""",(self.id,tag,))
                res = c.fetchone()
                if res is None:
                    c.execute("""INSERT INTO tag (track,tag,value) VALUES (?,?,?)""",(self.id,tag,value,))
                    modified = True
                elif res[1]==value:
                    continue
                else:
                    c.execute("""UPDATE tag SET value=? WHERE track=? AND tag=?""",(value,track,tag,))
                    modified = True
            if modified:
                self.treedb.commit()

    def update(self,tags=True,checksum=True):
        """
        Update TreeDB sqlite database tree details
        """

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

    def match(self,values,fields=['directory','filename','tags']):
        tracks = []
        c = self.cursor
        for value in values.split(','):
            try:
                tag,value = value.split('=',1)
                c.execute(
                    """SELECT a.path,t.filename FROM album as a, track as t, tag as x WHERE t.album=a.id AND x.track=t.id AND x.tag=? AND x.value LIKE ?""",
                    (tag,'%%%s%%' % value,),
                )
                tracks.extend(os.sep.join([r[0],r[1]]) for r in c.fetchall())
                continue

            except ValueError:
                pass

            if 'filename' in fields:
                c.execute(
                    """SELECT a.path,t.filename FROM album as a, track as t WHERE t.album=a.id AND t.filename LIKE ?""",
                    ('%%%s%%' % value,),
                )
                tracks.extend(os.sep.join([r[0],r[1]]) for r in c.fetchall())
            if 'directory' in fields:
                c.execute(
                    """SELECT a.path,t.filename FROM album as a, track as t WHERE t.album=a.id AND a.path LIKE ?""",
                    ('%%%s%%' % value,),
                )
                tracks.extend(os.sep.join([r[0],r[1]]) for r in c.fetchall())
            if 'tags' in fields:

                c.execute(
                    """SELECT a.path,t.filename FROM album as a, track as t, tag as x WHERE t.album=a.id AND x.track=t.id AND x.value LIKE ?""",
                    ('%%%s%%' % value,),
                )
                tracks.extend(os.sep.join([r[0],r[1]]) for r in c.fetchall())

        return sorted(set(tracks))

    def get_tags(self,path):
        c = self.cursor
        directory = os.path.dirname(path)
        filename = os.path.basename(path)
        c.execute(
            """SELECT tag,value FROM tag WHERE track = (
                 SELECT t.id FROM track as t, album as a WHERE a.id=t.album AND a.path=? AND t.filename=?
            )""",
            (directory,filename,)
        )
        return dict((r[0],r[1]) for r in c.fetchall())

    def summary(self,fields=['tags','tracks','albums']):
        """
        Collect a summary of database contents to a dictionary.
        """

        if not isinstance(fields,set):
            fields = set(fields)
        summary = {}
        c = self.cursor

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
