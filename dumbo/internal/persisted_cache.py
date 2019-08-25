from dataclasses import dataclass, Field

from persistent import Persistent
from persistent.mapping import PersistentMapping

from transaction import TransactionManager

from ZODB import DB
from ZODB.FileStorage.FileStorage import FileStorage

import numpy as np


class CachedValue(Persistent):
    def unlink(self):
        # This value is about to not be part of the cache anymore.
        # Deal with it (by removing auxiliary files etc).
        pass


@dataclass(unsafe_hash=True)
class ExternallyCachedValue(CachedValue):
    path: str

    def load(self):
        return None


@dataclass(unsafe_hash=True)
class DBCachedValue(CachedValue):
    value: object


class ExternallyCachedNumPyValue(CachedValue):
    def load(self):
        return np.load(self.path)

    def unlink(self):
        # TODO: delete the file.
        pass

@dataclass
class DumboPersistedCacheStorage(Persistent):
    external_cache_id: int
    vid_to_cached_value: PersistentMapping

    def __init__(self):
        self.vid_to_cached_value = PersistentMapping()
        self.external_cache_id = 0

    def get_new_external_id(self) -> str:
        drawn_external_cache_id = self.external_cache_id
        self.external_cache_id += 1
        return f"{drawn_external_cache_id:010}"


# TODO: to repr method
@dataclass
class DumboPersistedCache:
    storage: DumboPersistedCacheStorage
    transaction_manager: TransactionManager
    db: DB

    @staticmethod
    def from_memory():
        db = DB(None)
        return DumboPersistedCache(db)

    @staticmethod
    def from_file(path=None):
        if path is None:
            path = "dumbo_persisted_cache"
        db = DB(FileStorage(path))
        return DumboPersistedCache(db)

    def __init__(self, db):
        self.db = db
        self.transaction_manager = TransactionManager()

        connection = db.open(self.transaction_manager)
        root = connection.root

        self.storage = None

        if hasattr(root, 'storage'):
            self.storage = root.storage
        else:
            self.storage = DumboPersistedCacheStorage()
            with self.transaction_manager:
                root.storage = self.storage

    def cache_value(self, vid, value):
        return DBCachedValue(value)

    def update(self, vid, value):
        # TODO: value: None should just remove the entry, I think
        with self.transaction_manager:
            existing_cached_value = self.storage.vid_to_cached_value.get(vid)
            if existing_cached_value is not None:
                # assert isinstance(existing_cached_value, CachedValue)
                existing_cached_value.unlink()

            # TODO: logic to decide whether to store the value at all or not depending
            # on computational budget.
            self.storage.vid_to_cached_value[vid] = self.cache_value(vid, value)

    def get_cached_value(self, vid):
        return self.storage.vid_to_cached_value.get(vid)
