"""
Musa configuration database
"""

import os

from musa.sqlite import SqliteDB,SqliteDBError

DEFAULT_CONFIG_PATH = os.path.join(os.getenv('HOME'),'.musa','config.sqlite')

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
]

class MusaConfigDB(SqliteDB):
    def __init__(self,path=None):
        self.path = path is not None and path or DEFAULT_CONFIG_PATH
        SqliteDB.__init__(self,self.path,CONFIG_SQL,foreign_keys=True)

    def __getitem__(self,key):
        c = self.cursor
        c.execute("""SELECT value FROM settings WHERE key=?""",(key,))
        res = c.fetchone()
        if res is not None:
            return res[0]
        raise KeyError('No such value in settings: %s' % key)

    def __setitem__(self,key,value):
        c = self.cursor
        c.execute("""DELETE FROM settings WHERE key=?""", (key,))
        c.execute("""INSERT INTO settings (key,value) VALUES (?,?)""",(key,value,))
        self.commit()

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
        return dict((r[0],r[1]) for r in c.fetchall())

    def values(self):
        c = self.cursor
        c.execute("""SELECT value FROM settings""")
        return [r[0] for r in c.fetchall()]


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

if __name__ == '__main__':
    mcd = MusaConfigDB()
    mcd['threads'] = '0xff'
    value = mcd['threads']
    print type(value),value
    for t in ('/music/m4a','/music/mp3'):
        mcd.add_tree(t)
    print mcd.keys()
    print mcd.items()
    print mcd.values()
    print mcd.has_key('threads')
    print mcd.get_trees()

