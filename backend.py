import shelve
import os.path

class Backend():

    def __init__(self):
        self.db = shelve.open(os.path.join(os.path.dirname(__file__), "db/db_backend"), writeback=True)

        if not self.db.has_key('backend'):
            print('Creating new backend db')
            self.db['backend'] = dict(password=None, key=None)
            self._db_flush()

    def _db_flush(self):
        self.db.sync()
        self.db.close()
        self.db = shelve.open(os.path.join(os.path.dirname(__file__), "db/db_backend"), writeback=True)

    def _get_password(self):
        return self.db['backend']['password']

    def set_password(self, password):
        self.db['backend']['password'] = password
        self._db_flush()

    def is_password_set(self):
        return self.db['backend']['password'] <> None

    def verify_password(self, password):
        return self._get_password() == password

    def get_key(self):
        return self.db['backend']['key']

    def set_key(self, key):
        self.db['backend']['key'] = key
        self._db_flush()

    def is_key_set(self):
        return self.db['backend']['key'] <> None

    def verify_key(self, key):
        return self.get_key() == key




