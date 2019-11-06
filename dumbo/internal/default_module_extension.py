import sys
import pickle
from dataclasses import dataclass

import objproxies

from typing import Optional, Tuple

from dumbo.internal.cached_values import ExternallyCachedFilePath, CachedValue, ExternallyCachedValue, DBCachedValue
from dumbo.internal.module_extension import ModuleExtension, ObjectSaver

import hashlib

from dumbo.internal.reflection import get_type_qualified_name

MAX_PICKLE_SIZE = 2 ** 30


@dataclass
class CachedTuple(CachedValue):
    values: Tuple[CachedValue, ...]

    def load(self):
        return tuple(item.load() for item in self.values)

    def unlink(self):
        for item in self.values:
            item.unlink()


class DefaultObjectSaver(ObjectSaver):
    def __init__(self, value, pickled_bytes):
        self.value = value
        self.pickled_bytes = pickled_bytes

    def get_estimated_size(self) -> Optional[int]:
        return len(self.pickled_bytes)

    def compute_digest(self):
        return hashlib.md5(self.pickled_bytes).digest()

    def cache_value(self, external_path_builder: Optional[ExternallyCachedFilePath]) -> Optional[CachedValue]:
        if external_path_builder is not None:
            external_path = external_path_builder.build(get_type_qualified_name(self.value), "pickle")
            with open(external_path, "bw") as external_file:
                external_file.write(self.pickled_bytes)

            return ExternallyCachedValue(external_path)

        # TODO: catch transactions error for objects that cannot be pickled here?
        return DBCachedValue(self.value)


class DefaultTupleObjectSaver(ObjectSaver):
    def __init__(self, object_savers: Tuple[ObjectSaver]):
        self.object_savers = object_savers

    def get_estimated_size(self) -> int:
        return sum(object_saver.get_estimated_size() for object_saver in self.object_savers)

    def compute_digest(self):
        hash_method = hashlib.md5()
        for object_saver in self.object_savers:
            hash_method.update(object_saver.compute_digest())
        return hash_method.digest()

    def cache_value(self, external_path_builder: Optional[ExternallyCachedFilePath]) -> Optional[CachedValue]:
        return CachedTuple(
            tuple(
                object_saver.cache_value(
                    ExternallyCachedFilePath.for_tuple_item(external_path_builder, i)
                )
                for i, object_saver in enumerate(self.object_savers)
            )
        )


class DefaultModuleExtension(ModuleExtension):
    def supports(self, value):
        return True

    def try_pickle(self, value):
        try:
            return pickle.dumps(value)
        except pickle.PicklingError as err:
            # TODO: log err
            print(err)
            return None

    def get_object_saver(self, value) -> Optional[ObjectSaver]:
        if isinstance(value, tuple):
            return DefaultTupleObjectSaver(
                tuple(
                    self.module_registry.get_object_saver(item)
                    for item in value
                )
            )

        try:
            pickled_bytes = pickle.dumps(value)
        except pickle.PicklingError as err:
            # TODO: log err
            print(err)
            return None

        if len(pickled_bytes) > MAX_PICKLE_SIZE:
            # TODO: log
            return None

        return DefaultObjectSaver(value, pickled_bytes)

    def wrap_return_value(self, value):
        # Treat tuples different for functions returning multiple values.
        # We usually want to wrap them separately.
        if isinstance(value, tuple):
            return tuple(self.module_registry.wrap_return_value(item) for item in value)

        if not isinstance(value, objproxies.ObjectProxy):
            return objproxies.ObjectProxy(value)

        return objproxies.ObjectProxy(value.__subject__)
