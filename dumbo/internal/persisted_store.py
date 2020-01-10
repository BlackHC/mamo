import os
import pickle
from dataclasses import dataclass
from typing import Optional, Dict

from ZODB import DB
from ZODB.FileStorage.FileStorage import FileStorage
from persistent import Persistent
from persistent.mapping import PersistentMapping
from transaction import TransactionManager

from dumbo.internal.bimap import PersistentBimap
from dumbo.internal.cached_values import CachedValue, ExternallyCachedFilePath, ExternallyCachedValue
from dumbo.internal.fingerprints import Fingerprint
from dumbo.internal.identities import ValueIdentity
from dumbo.internal.module_extension import MODULE_EXTENSIONS

MAX_DB_CACHED_VALUE_SIZE = 1024


class BuiltinExternallyCachedValue(ExternallyCachedValue):
    def load(self):
        with open(self.path, "rb") as external_file:
            return pickle.load(external_file)


@dataclass
class DumboPersistedCacheStorage(Persistent):
    external_cache_id: int
    vid_to_cached_value: Dict[ValueIdentity, CachedValue]
    vid_to_fingerprint: Dict[ValueIdentity, Fingerprint]
    tag_to_vid: PersistentBimap[str, ValueIdentity]

    def __init__(self):
        self.vid_to_cached_value = PersistentMapping()
        self.vid_to_fingerprint = PersistentMapping()
        self.tag_to_vid = PersistentBimap()
        self.external_cache_id = 0

    def get_new_external_id(self):
        drawn_external_cache_id = self.external_cache_id
        self.external_cache_id += 1
        return f"{drawn_external_cache_id:010}"


# TODO: to repr method
@dataclass
class PersistedStore:
    storage: DumboPersistedCacheStorage
    transaction_manager: TransactionManager
    db: DB
    path: str
    externally_cached_path: str

    @staticmethod
    def from_memory():
        db = DB(None)
        return PersistedStore(db, None, None)

    @staticmethod
    def from_file(path: Optional[str] = None, externally_cached_path: Optional[str] = None):
        if path is None:
            path = "./"
        if externally_cached_path is None:
            externally_cached_path = path

        # Create directories if they haven't been created yet.
        os.makedirs(path, exist_ok=True)
        os.makedirs(externally_cached_path, exist_ok=True)

        # TODO: log the paths?
        # TODO: in general, make properties available for quering in the console/Jupyter?

        db = DB(FileStorage(os.path.join(path, "dumbo_store")))
        return PersistedStore(db, path, externally_cached_path)

    def __init__(self, db: DB, path: Optional[str], externally_cached_path: Optional[str]):
        self.db = db
        self.path = os.path.abspath(path) if path else path
        self.externally_cached_path = (
            os.path.abspath(externally_cached_path) if externally_cached_path else externally_cached_path
        )
        self.transaction_manager = TransactionManager()

        connection = db.open(self.transaction_manager)
        root = connection.root

        if not hasattr(root, "storage"):
            with self.transaction_manager:
                root.storage = DumboPersistedCacheStorage()

        self.storage = root.storage

    def testing_close(self):
        self.db.close()
        self.transaction_manager.clearSynchs()

    def get_new_external_id(self):
        return self.storage.get_new_external_id()

    def try_create_cached_value(
        self, vid: ValueIdentity, value: object
    ) -> Optional[CachedValue]:
        assert value is not None
        object_saver = MODULE_EXTENSIONS.get_object_saver(value)
        if not object_saver:
            # TODO: log?
            return None

        estimated_size = object_saver.get_estimated_size()
        if estimated_size is None:
            # TODO: log?
            return None

        external_path_builder = None
        # If we exceed a reasonable size, we don't store the result in the DB.
        # However, if we are memory-only, we don't cache in external files.
        if estimated_size > MAX_DB_CACHED_VALUE_SIZE and self.externally_cached_path is not None:
            external_path_builder = ExternallyCachedFilePath(
                self.externally_cached_path, self.get_new_external_id(), vid.get_external_info()
            )

        cached_value = object_saver.cache_value(external_path_builder)
        if not cached_value:
            # TODO: log?
            return None

        return cached_value

    def add(self, vid: ValueIdentity, value: object, fingerprint: Fingerprint):
        assert value is not None

        with self.transaction_manager:
            existing_cached_value = self.storage.vid_to_cached_value.get(vid)
            if existing_cached_value:
                # assert isinstance(existing_cached_value, CachedValue)
                # TODO: add test cases for unlinking!!!
                existing_cached_value.unlink()

            # TODO: logic to decide whether to store the value at all or not depending
            # on computational budget.

            # TODO: this is currently holding object proxies sometimes
            # Which makes weakref collection hard!
            # # TODO: ugly: need to unwrap object proxy, fix this!
            # assert isinstance(value.value, ObjectProxy)
            # value = dataclasses.replace(value, value=value.value.__subject__)

            cached_value = self.try_create_cached_value(vid, value)
            if cached_value:
                self.storage.vid_to_cached_value[vid] = cached_value
                self.storage.vid_to_fingerprint[vid] = fingerprint
            else:
                if existing_cached_value:
                    del self.storage.vid_to_cached_value[vid]
                    del self.storage.vid_to_fingerprint[vid]

    def remove_vid(self, vid: ValueIdentity):
        with self.transaction_manager:
            value = self.storage.vid_to_cached_value.get(vid)
            if value is not None:
                # TODO: add test cases for unlinking!!!
                value.unlink()

                del self.storage.vid_to_cached_value[vid]
                del self.storage.vid_to_fingerprint[vid]

    def get_vids(self):
        return set(self.storage.vid_to_cached_value.keys())

    def get_cached_value(self, vid: ValueIdentity):
        return self.storage.vid_to_cached_value.get(vid)

    def load_value(self, vid: ValueIdentity):
        cached_value = self.get_cached_value(vid)
        if not cached_value:
            return None

        # Load value
        loaded_value = cached_value.load()
        wrapped_value = MODULE_EXTENSIONS.wrap_return_value(loaded_value)
        return wrapped_value

    def get_fingerprint(self, vid: ValueIdentity):
        return self.storage.vid_to_fingerprint.get(vid)

    def tag(self, tag_name: str, vid: Optional[ValueIdentity]):
        with self.transaction_manager:
            self.storage.tag_to_vid.update(tag_name, vid)

    def get_tag_vid(self, tag_name) -> Optional[ValueIdentity]:
        return self.storage.tag_to_vid.get_value(tag_name)

    def has_vid(self, vid):
        return vid in self.storage.vid_to_cached_value
