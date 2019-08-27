import sys
from abc import ABC
from dataclasses import dataclass
from typing import Optional

from persistent import Persistent
from persistent.mapping import PersistentMapping

from dumbo.internal.identities import ValueIdentity

from transaction import TransactionManager

from ZODB import DB
from ZODB.FileStorage.FileStorage import FileStorage

from dumbo.internal.reflection import ModuleRegistry

import os
import pickle

MAX_DB_CACHED_VALUE_SIZE = 1024


class CachedValue(Persistent):
    def unlink(self):
        # This value is about to not be part of the cache anymore.
        # Deal with it (by removing auxiliary files etc).
        pass

    def load(self):
        raise NotImplementedError()


@dataclass
class ExternallyCachedFilePathBuilder:
    path: str
    external_id: str
    vid_info: str

    def build(self, cache_info, ext):
        return f'{self.path}{self.vid_info}_{cache_info}_{self.external_id}{ext}'


class ModuleCacheHandler:
    def get_estimated_size(self, value) -> int:
        raise NotImplementedError()

    def cache(self, value, external_path_builder: Optional[ExternallyCachedFilePathBuilder]) -> CachedValue:
        raise NotImplementedError()



@dataclass(unsafe_hash=True)
class ExternallyCachedValue(CachedValue, ABC):
    path: str

    def unlink(self):
        unlinked_path = self.path + '.unlinked'
        # TODO: shall we pass the vid as argument and store it in a file next to
        # the unlinked entry?
        os.rename(self.path, unlinked_path)


@dataclass(unsafe_hash=True)
class DBCachedValue(CachedValue, ABC):
    value: object

    def load(self):
        return self.value


class BuiltinExternallyCachedValue(ExternallyCachedValue):
    def load(self):
        with open(self.path, "rb") as external_file:
            return pickle.load(external_file)


class PicklingCacheHandler(ModuleCacheHandler):
    def get_estimated_size(self, value):
        # This is a rather bad approximation that does not take into account
        # the size of elements.
        return sys.getsizeof(value)

    def cache(self, value, external_path_builder: ExternallyCachedFilePathBuilder):
        if external_path_builder is not None:
            try:
                pickled_bytes = pickle.dumps(value)
            except pickle.PicklingError as err:
                # TODO: log err
                print(err)
                return None

            external_path = external_path_builder.build(type(value), 'pickle')
            with open(external_path, "bw") as external_file:
                external_file.write(pickled_bytes)
            return ExternallyCachedValue(external_path)

        # TODO: catch transactions error for objects that cannot be pickled here?
        return DBCachedValue(value)


CACHED_VALUE_REGISTRY: ModuleRegistry[ModuleCacheHandler] = ModuleRegistry()


@dataclass
class DumboPersistedCacheStorage(Persistent):
    external_cache_id: int
    vid_to_cached_value: PersistentMapping[ValueIdentity, CachedValue]
    tag_to_vid: PersistentMapping[str, ValueIdentity]

    def __init__(self):
        self.vid_to_cached_value = PersistentMapping()
        self.tag_to_vid = PersistentMapping()
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
    def from_file(path=None):
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

    def get_new_external_id(self):
        return self.storage.get_new_external_id()

    def try_create_cached_value(self, vid: ValueIdentity, value):
        cache_handler = CACHED_VALUE_REGISTRY.get(value)

        # TODO: handle Nones
        # maybe add a supports(value) method to avoid all the repeated checks?
        if cache_handler is None:
            cache_handler = PicklingCacheHandler()

        estimated_size = cache_handler.get_estimated_size(value)
        external_path_builder = None
        if estimated_size > MAX_DB_CACHED_VALUE_SIZE:
            external_path_builder = ExternallyCachedFilePathBuilder(
                self.path, self.get_new_external_id(),
                vid.get_external_info()
            )

        cached_value = cache_handler.cache(value, external_path_builder)

        # TODO: handle cached_value is None and log?!!
        return cached_value

    def update(self, vid, value):
        # TODO: value: None should just remove the entry, I think
        # need to also update tags!

        with self.transaction_manager:
            existing_cached_value = self.storage.vid_to_cached_value.get(vid)
            if existing_cached_value is not None:
                # assert isinstance(existing_cached_value, CachedValue)
                existing_cached_value.unlink()

            # TODO: logic to decide whether to store the value at all or not depending
            # on computational budget.

            cached_value = self.try_create_cached_value(vid, value)
            if cached_value is not None:
                self.storage.vid_to_cached_value[vid] = cached_value

    def get_cached_value(self, vid) -> CachedValue:
        return self.storage.vid_to_cached_value.get(vid)

    def get_value(self, vid):
        cached_value = self.get_cached_value(vid)
        if cached_value is None:
            return None

        # Load value
        return cached_value.load()

    def tag(self, vid, tag_name):
        if vid is None and tag_name in self.storage.tag_to_vid:
            del self.storage.tag_to_vid[tag_name]

        if vid in self.storage.vid_to_cached_value:
            self.storage.tag_to_vid[tag_name] = vid
        # TODO: log?

    def get_tag_vid(self, tag_name):
        return self.storage.tag_to_vid.get(tag_name)

    # TODO: sometimes I use try_get and sometimes just get!
