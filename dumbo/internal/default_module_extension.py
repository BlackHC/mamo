import sys
import pickle
import objproxies

from typing import Optional

from dumbo.internal.cached_values import ExternallyCachedFilePath, CachedValue, ExternallyCachedValue, \
    DBCachedValue
from dumbo.internal.module_extension import ModuleExtension, MAX_FINGERPRINT_LENGTH, MODULE_EXTENSIONS

import hashlib


MAX_PICKLE_SIZE = 2**30


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

        # TODO: add a special fingerprint class, so we can differentiate between
        # digests and pickled values. (which can be useful for debugging)
        return hashlib.md5(pickled_bytes).digest()

    def get_estimated_size(self, value) -> int:
        # This is a rather bad approximation that does not take into account
        # the size of elements.
        return sys.getsizeof(value)

    def cache_value(self, value, external_path_builder: Optional[ExternallyCachedFilePath]) -> CachedValue:
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

    def wrap_return_value(self, value, wrap_return_value):
        # Treat tuples different for functions returning multiple values.
        # We usually want to wrap them separately.
        if isinstance(value, tuple):
            return tuple(wrap_return_value(item) for item in value)

        if not isinstance(value, objproxies.ObjectProxy):
            return objproxies.ObjectProxy(value)

        return objproxies.ObjectProxy(value.__subject__)

