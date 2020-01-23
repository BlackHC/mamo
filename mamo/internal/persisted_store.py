import os
import pickle
from dataclasses import dataclass
from typing import Optional, Dict

from ZODB import DB
from ZODB.FileStorage.FileStorage import FileStorage
from persistent import Persistent
from persistent.mapping import PersistentMapping
from transaction import TransactionManager

from mamo.internal.bimap import PersistentBimap
from mamo.internal.cached_values import CachedValue, ExternallyCachedFilePath, ExternallyCachedValue
from mamo.internal.fingerprints import Fingerprint
from mamo.internal.identities import ValueIdentity
from mamo.internal.module_extension import MODULE_EXTENSIONS
from mamo.internal.result_metadata import ResultMetadata
from mamo.internal.stopwatch_context import StopwatchContext
from mamo.internal.weakref_utils import ObjectProxy

MAX_DB_CACHED_VALUE_SIZE = 1024


@dataclass
class MamoPersistedCacheStorage(Persistent):
    external_cache_id: int
    vid_to_cached_value: Dict[ValueIdentity, CachedValue]
    vid_to_fingerprint: Dict[ValueIdentity, Fingerprint]
    vid_to_result_metadata: Dict[ValueIdentity, ResultMetadata]
    tag_to_vid: PersistentBimap[str, ValueIdentity]

    def __init__(self):
        self.vid_to_cached_value = PersistentMapping()
        self.vid_to_fingerprint = PersistentMapping()
        self.vid_to_result_metadata = PersistentMapping()
        self.tag_to_vid = PersistentBimap()
        self.external_cache_id = 0

    def get_new_external_id(self):
        drawn_external_cache_id = self.external_cache_id
        self.external_cache_id += 1
        return f"{drawn_external_cache_id:010}"


@dataclass
class CacheOperationResult:
    cached_value: CachedValue
    result_size: int
    stored_size: int
    save_duration: float


# TODO: to repr method
@dataclass
class PersistedStore:
    storage: MamoPersistedCacheStorage
    transaction_manager: TransactionManager
    db: DB
    path: str
    externally_cached_path: str

    @staticmethod
    def from_memory():
        db = DB(None, large_record_size=64*(1 << 20))
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

        db = DB(FileStorage(os.path.join(path, "mamo_store")))
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
                root.storage = MamoPersistedCacheStorage()

        self.storage = root.storage

    def close(self):
        self.db.close()
        self.transaction_manager.clearSynchs()

    def get_new_external_id(self):
        return self.storage.get_new_external_id()

    def try_create_cached_value(
            self, vid: ValueIdentity, value: object
    ) -> Optional[CacheOperationResult]:
        with StopwatchContext() as stopwatch:
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
                return None

            stored_size = cached_value.get_stored_size()

        return CacheOperationResult(cached_value=cached_value, result_size=estimated_size, stored_size=stored_size,
                                    save_duration=stopwatch.elapsed_time)

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

            # Unwrap object proxy
            if isinstance(value, ObjectProxy):
                value = value.__subject__

            result = self.try_create_cached_value(vid, value)
            if result:
                self.storage.vid_to_cached_value[vid] = result.cached_value
                self.storage.vid_to_fingerprint[vid] = fingerprint

                result_metadata = ResultMetadata(result_size=result.result_size,
                                                 stored_size=result.stored_size,
                                                 save_duration=result.save_duration)
                self.storage.vid_to_result_metadata[vid] = result_metadata
            else:
                # TODO: log? result is None means caching has failed!
                if existing_cached_value:
                    del self.storage.vid_to_cached_value[vid]
                    del self.storage.vid_to_fingerprint[vid]
                    del self.storage.vid_to_result_metadata[vid]

    def remove_vid(self, vid: ValueIdentity):
        value = self.storage.vid_to_cached_value.get(vid)
        if value is not None:
            # TODO: add test cases for unlinking!!!
            with self.transaction_manager:
                del self.storage.vid_to_cached_value[vid]
                del self.storage.vid_to_fingerprint[vid]
                del self.storage.vid_to_result_metadata[vid]
                value.unlink()

    def get_vids(self):
        return set(self.storage.vid_to_cached_value.keys())

    def get_cached_value(self, vid: ValueIdentity):
        return self.storage.vid_to_cached_value.get(vid)

    def load_value(self, vid: ValueIdentity):
        cached_value = self.get_cached_value(vid)
        if not cached_value:
            return None

        # Load value
        with StopwatchContext() as stopwatch:
            loaded_value = cached_value.load()
            wrapped_value = MODULE_EXTENSIONS.wrap_return_value(loaded_value)

        metadata = self.get_result_metadata(vid)
        with self.transaction_manager:
            metadata.total_load_durations += stopwatch.elapsed_time
            metadata.num_loads += 1

        return wrapped_value

    def get_fingerprint(self, vid: ValueIdentity) -> Fingerprint:
        return self.storage.vid_to_fingerprint.get(vid)

    def get_result_metadata(self, vid: ValueIdentity) -> ResultMetadata:
        return self.storage.vid_to_result_metadata.get(vid)

    def tag(self, tag_name: str, vid: Optional[ValueIdentity]):
        with self.transaction_manager:
            self.storage.tag_to_vid.update(tag_name, vid)

    def get_tag_vid(self, tag_name) -> Optional[ValueIdentity]:
        return self.storage.tag_to_vid.get_value(tag_name)

    def get_tag_name(self, vid: ValueIdentity) -> Optional[str]:
        return self.storage.tag_to_vid.get_key(vid)

    def has_vid(self, vid):
        return vid in self.storage.vid_to_cached_value
