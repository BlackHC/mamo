from dataclasses import dataclass
from typing import Optional

from persistent import Persistent
from persistent.mapping import PersistentMapping

from dumbo.internal.cached_values import CachedValue, ExternallyCachedFilePath, ExternallyCachedValue
from dumbo.internal.identities import ValueCIDIdentity, StoredResult
from dumbo.internal.bimap import PersistentBimap

from transaction import TransactionManager

from ZODB import DB
from ZODB.FileStorage.FileStorage import FileStorage

import os
import pickle

from dumbo.internal.module_extension import MODULE_EXTENSIONS

MAX_DB_CACHED_VALUE_SIZE = 1024


class BuiltinExternallyCachedValue(ExternallyCachedValue):
    def load(self):
        with open(self.path, "rb") as external_file:
            return pickle.load(external_file)


@dataclass
class DumboPersistedCacheStorage(Persistent):
    external_cache_id: int
    vid_to_cached_value: PersistentMapping
    tag_to_vid: PersistentBimap[str, ValueCIDIdentity]

    def __init__(self):
        self.vid_to_cached_value = PersistentMapping()
        self.tag_to_vid = PersistentBimap()
        self.external_cache_id = 0

    def get_new_external_id(self):
        drawn_external_cache_id = self.external_cache_id
        self.external_cache_id += 1
        return f"{drawn_external_cache_id:010}"


# TODO: to repr method
@dataclass
class DumboPersistedCache:
    storage: DumboPersistedCacheStorage
    transaction_manager: TransactionManager
    db: DB
    path: str

    @staticmethod
    def from_memory():
        db = DB(None)
        return DumboPersistedCache(db, None)

    @staticmethod
    def from_file(path: Optional[str] = None):
        if path is None:
            path = "./"
        db = DB(FileStorage(path + "dumbo_persisted_cache"))
        return DumboPersistedCache(db, path)

    def __init__(self, db: DB, path: Optional[str]):
        self.db = db
        self.path = os.path.abspath(path) if path else path
        self.transaction_manager = TransactionManager()

        connection = db.open(self.transaction_manager)
        root = connection.root

        if not hasattr(root, 'storage'):
            with self.transaction_manager:
                root.storage = DumboPersistedCacheStorage()

        self.storage = root.storage

    def testing_close(self):
        self.db.close()
        self.transaction_manager.clearSynchs()

    def get_new_external_id(self):
        return self.storage.get_new_external_id()

    def try_create_cached_value(self, vid: ValueCIDIdentity, value: StoredResult) -> Optional[StoredResult[CachedValue]]:
        estimated_size = MODULE_EXTENSIONS.get_estimated_size(value)
        if estimated_size is None:
            # TODO log?
            return None

        external_path_builder = None
        # If we exceed a reasonable size, we don't store the result in the DB.
        # However, if we are memory-only, we don't cache in external files.
        if estimated_size > MAX_DB_CACHED_VALUE_SIZE and self.path is not None:
            external_path_builder = ExternallyCachedFilePath(
                self.path, self.get_new_external_id(),
                vid.get_external_info()
            )

        cached_value = MODULE_EXTENSIONS.cache_value(value.value, external_path_builder)

        # TODO: handle cached_value is None and log?!!
        return StoredResult(cached_value, value.func_fingerprint)

    def update(self, vid: ValueCIDIdentity, value: StoredResult):
        with self.transaction_manager:
            existing_cached_value = self.storage.vid_to_cached_value.get(vid)
            if existing_cached_value is not None:
                # assert isinstance(existing_cached_value, CachedValue)
                existing_cached_value.unlink()

            if value is None:
                del self.storage.vid_to_cached_value[vid]

                # Also remove any existing tags.
                self.storage.tag_to_vid.del_value(vid)
            else:
                # TODO: logic to decide whether to store the value at all or not depending
                # on computational budget.

                cached_value = self.try_create_cached_value(vid, value)
                if cached_value is not None:
                    self.storage.vid_to_cached_value[vid] = cached_value
                else:
                    if existing_cached_value:
                        del self.storage.vid_to_cached_value[vid]

    def get_cached_value(self, vid) -> Optional[StoredResult[CachedValue]]:
        return self.storage.vid_to_cached_value.get(vid)

    def get_stored_result(self, vid):
        cached_value = self.get_cached_value(vid)
        if cached_value is None:
            return None

        # Load value
        return StoredResult(cached_value.value.load(), cached_value.func_fingerprint)

    def tag(self, tag_name: str, vid: ValueCIDIdentity):
        if vid is not None and vid not in self.storage.vid_to_cached_value:
            # TODO: log?
            return

        with self.transaction_manager:
            self.storage.tag_to_vid.update(tag_name, vid)

    def get_tag_vid(self, tag_name) -> Optional[ValueCIDIdentity]:
        return self.storage.tag_to_vid.get_value(tag_name)
