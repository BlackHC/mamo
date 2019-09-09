import sys
import pickle
from dataclasses import dataclass

import objproxies

from typing import Optional, Tuple

from dumbo.internal.cached_values import ExternallyCachedFilePath, CachedValue, ExternallyCachedValue, \
    DBCachedValue
from dumbo.internal.module_extension import ModuleExtension, MAX_FINGERPRINT_LENGTH, MODULE_EXTENSIONS

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

    def compute_fingerprint(self, value):
        if self.get_estimated_size(value) > MAX_PICKLE_SIZE:
            # TODO: log
            return None

        pickled_bytes = self.try_pickle(value)
        if len(pickled_bytes) <= MAX_FINGERPRINT_LENGTH:
            return value

        if isinstance(value, tuple):
            hash_method = hashlib.md5()
            for item in value:
                hash_method.update(self.module_registry.compute_fingerprint(item))
            return hash_method.digest()

        # TODO: add a special fingerprint class, so we can differentiate between
        # digests and pickled values. (which can be useful for debugging)
        return hashlib.md5(pickled_bytes).digest()

    def get_estimated_size(self, value) -> int:
        # This is a rather bad approximation that does not take into account
        # the size of elements.
        if isinstance(value, tuple):
            return sum(self.module_registry.get_estimated_size(item) for item in value)
        return sys.getsizeof(value)

    def cache_value(self, value, external_path_builder: Optional[ExternallyCachedFilePath]):
        if isinstance(value, tuple):
            return CachedTuple(
                tuple(self.module_registry.cache_value(
                    item, ExternallyCachedFilePath.for_tuple_item(external_path_builder, i))
                      for i, item in enumerate(value)))

        if external_path_builder is not None:
            try:
                pickled_bytes = pickle.dumps(value)
            except pickle.PicklingError as err:
                # TODO: log err
                print(err)
                return None

            external_path = external_path_builder.build(get_type_qualified_name(value), 'pickle')
            with open(external_path, "bw") as external_file:
                external_file.write(pickled_bytes)

            return ExternallyCachedValue(external_path)

        # TODO: catch transactions error for objects that cannot be pickled here?
        return DBCachedValue(value)

    def wrap_return_value(self, value):
        # Treat tuples different for functions returning multiple values.
        # We usually want to wrap them separately.
        if isinstance(value, tuple):
            return tuple(self.module_registry.wrap_return_value(item) for item in value)

        if not isinstance(value, objproxies.ObjectProxy):
            return objproxies.ObjectProxy(value)

        return objproxies.ObjectProxy(value.__subject__)
