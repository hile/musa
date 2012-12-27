"""
Generic sqlite database backend for musa tools
"""

import os,sqlite3,logging

class SqliteDBError(Exception):
    """
    Exception raised by SQLiteDatabase errors.
    """
    def __str__(self):
        return self.args[0]

class SqliteDB(object):
    """
    Implementation of sqlite3 database singleton instances
    """
    __instances = {}
    def __init__(self,db_path,queries=[],foreign_keys=True):
        """
        Initialize a new sqlite database to given db_path. You can setup the database tables
        by passing the 'queries' attribute and enforce PRAGMA foreign_keys=ON by setting
        foreign_keys to True (default)
        """
        if not SqliteDB.__instances.has_key(db_path):
            SqliteDB.__instances[db_path] = SqliteDB.DBInstance(db_path,queries,foreign_keys)
        self.__dict__['SqliteDB.__instances'] = SqliteDB.__instances
        self.__dict__['db_path'] = db_path

    class DBInstance(object):
        """
        Singleton instance for accessing given database file
        """
        def __init__(self,db_path,queries,foreign_keys):
            self.db_path = db_path
            self.log = logging.getLogger('musa')
            if not os.path.isfile(db_path):
                dbdir = os.path.dirname(db_path)
                if not os.path.isdir(dbdir):
                    try:
                        os.makedirs(dbdir)
                    except OSError:
                        raise SqliteDBError('Error creating database directory: %s' % dbdir)

            self.conn = sqlite3.Connection(self.db_path)

            c = self.conn.cursor()
            if foreign_keys:
                c.execute('PRAGMA foreign_keys=ON')
                c.fetchone()

            if isinstance(queries,list):
                for q in queries:
                    try:
                        c.execute(q)
                    except sqlite3.OperationalError,emsg:
                        raise SqliteDBError('Error executing SQL:\n%s\n%s' % (q,emsg))
            del c

        def __del__(self):
            if hasattr(self,'conn') and self.conn is not None:
                self.conn.close()
                self.conn = None


    @property
    def conn(self):
        return self.__instances[self.db_path].conn

    @property
    def cursor(self):
        c = self.conn.cursor()
        if c is None:
            raise SqliteDBError('Could not get cursor to database')
        return c

    def rollback(self):
        """
        Rollback transaction
        """
        return self.conn.rollback()

    def commit(self):
        """
        Commit transaction
        """
        return self.conn.commit()

    def as_dict(self,cursor,result):
        """
        Return one query result from sqlite as dictionary with keys from
        cursor field descriptions.
        """
        if result is None:
            return None

        if not isinstance(cursor,sqlite3.Cursor):
            raise SqliteDBError('as_dict():  cursor must be a valid sqlite3 cursor')

        data = {}
        for i,k in enumerate([e[0] for e in cursor.description]):
            data[k] = result[i]
        return data

