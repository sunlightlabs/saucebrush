"""
    Saucebrush Emitters are filters that instead of modifying the record, output
    it in some manner.
"""

from saucebrush.filters import Filter

class Emitter(Filter):
    """ ABC for emitters

        All derived emitters must provide an emit_record(self, record) that
        takes a single record (python dictionary).

        Emitters can optionally define a close() method that is called after
        all records are processed (allowing database flushes, or printing of
        aggregate data).
    """

    def __init__(self):
        super(Emitter, self).__init__()

    def process_record(self, record):
        self.emit_record(record)
        return record

    def emit_record(self, record):
        """ Abstract method to be overridden.

            Called with a single record, should "emit" the record unmodified.
        """
        raise NotImplementedError('emit_record not defined in ' +
                                  self.__class__.__name__)

    def done(self):
        """ No-op Method to be overridden.

            Called when all processing is complete
        """
        pass


class DebugEmitter(Emitter):
    """ Emitter that prints raw records to a file, useful for debugging.

        DebugEmitter() by default prints to stdout.
        DebugEmitter(open('test', 'w')) would print to a file named test
    """
    def __init__(self, outfile=None):
        super(DebugEmitter, self).__init__()
        if not outfile:
            import sys
            self._outfile = sys.stdout
        else:
            self._outfile = outfile

    def emit_record(self, record):
        self._outfile.write(str(record) + '\n')


class CSVEmitter(Emitter):
    """ Emitter that writes records to a CSV file.

        CSVEmitter(open('output.csv','w'), ('id', 'name', 'phone'))  writes all
        records to a csvfile with the columns in the order specified.
    """

    def __init__(self, csvfile, fieldnames=None):
        super(CSVEmitter, self).__init__()
        import csv
        self._dictwriter = csv.DictWriter(csvfile, fieldnames)
        # write header row
        self._dictwriter.writerow(dict(zip(fieldnames, fieldnames)))

    def emit_record(self, record):
        self._dictwriter.writerow(record)


class SqliteEmitter(Emitter):
    """ Emitter that writes records to a SQLite database.

        SqliteEmitter('addressbook.db', 'friend') writes all records to the
        friends table in the SQLite database named addressbook.db

        (To have the emitter create the table, the fieldnames should be passed
        as a third parameter to SqliteEmitter.)
    """

    def __init__(self, dbname, table_name, fieldnames=None):
        super(SqliteEmitter, self).__init__()
        import sqlite3
        self._conn = sqlite3.connect(dbname)
        self._cursor = self._conn.cursor()
        self._table_name = table_name
        if fieldnames:
            create = "CREATE TABLE IF NOT EXISTS %s (%s)" % (table_name,
                ', '.join([' '.join((field, 'TEXT')) for field in fieldnames]))
            self._cursor.execute(create)

    def emit_record(self, record):
        # input should be escaped with ? if data isn't trusted
        qmarks = ','.join(('?',) * len(record))
        insert = 'INSERT INTO %s (%s) VALUES (%s)' % (self._table_name,
                                                      ','.join(record.keys()),
                                                      qmarks)
        self._cursor.execute(insert, record.values())

    def done(self):
        self._conn.commit()
        self._conn.close()


class SqlDumpEmitter(Emitter):
    """ Emitter that writes SQL INSERT statements.

        The output generated by the SqlDumpEmitter is intended to be used to
        populate a mySQL database.

        SqlDumpEmitter(open('addresses.sql', 'w'), 'friend', ('name', 'phone'))
        writes statements to addresses.sql to insert the data
        into the friends table.
    """

    def __init__(self, outfile, table_name, fieldnames):
        super(SqlDumpEmitter, self).__init__()
        self._fieldnames = fieldnames
        if not outfile:
            import sys
            self._outfile = sys.stderr
        else:
            self._outfile = outfile
        self._insert_str = "INSERT INTO `%s` (`%s`) VALUES (%%s);\n" % (
                            table_name, '`,`'.join(fieldnames))

    def quote(self, item):
        item = item.replace("\\","\\\\").replace("'","\\'").replace(chr(0),'0')
        return "'%s'" % item

    def emit_record(self, record):
        quoted_data = [self.quote(record[field]) for field in self._fieldnames]
        self._outfile.write(self._insert_str % ','.join(quoted_data))

    def done(self):
        self._outfile.close()


class DjangoModelEmitter(Emitter):
    """ Emitter that populates a table corresponding to a django model.

        Takes a django settings file, app label and model name and uses django
        to insert the records into the appropriate table.

        DjangoModelEmitter('settings.py', 'addressbook', 'friend') writes
        records to addressbook.models.friend model using database settings
        from settings.py.
    """
    def __init__(self, dj_settings, app_label, model_name):
        super(DjangoModelEmitter, self).__init__()
        from saucebrush.utils import get_django_model
        self._dbmodel = get_django_model(dj_settings, app_label, model_name)
        if not self._dbmodel:
            raise Exception("No such model: %s %s" % (app_label, model_name))

    def emit_record(self, record):
        self._dbmodel.objects.create(**record)


class MongoDBEmitter(Emitter):
    """ Emitter that creates a document in a MongoDB datastore
        
        The names of the database and collection in which the records will
        be inserted are required parameters. The host and port are optional,
        defaulting to 'localhost' and 27017, repectively.
    """
    def __init__(self, database, collection, host='localhost', port=27017, drop_collection=False):
        super(MongoDBEmitter, self).__init__()
        from pymongo.connection import Connection
        conn = Connection(host, port)
        db = conn[database]
        if drop_collection:
            db.drop_collection(collection)
        self.collection = db[collection]
    
    def emit_record(self, record):
        self.collection.insert(record)
    
    def done(self, record):
        pass
