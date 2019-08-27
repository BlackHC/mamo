import numpy as np
import hashlib
from dumbo.internal.reflection import FINGERPRINT_FUNCTION_REGISTRY
from dumbo.internal.persisted_cache import ModuleCacheHandler, ExternallyCachedValue, CACHED_VALUE_REGISTRY, ExternallyCachedFilePathBuilder, \
    CachedValue
from dumbo.internal.return_handlers import RETURN_HANDLER_REGISTRY
import sys

np_types = (np.ndarray, np.record, np.matrix, np.recarray, np.chararray, np.generic, np.memmap)

def hash_numpy(value):
    if isinstance(value, np_types):
        return hashlib.md5(value).digest()

    # TODO: log that we don't support a specific type?
    return None


FINGERPRINT_FUNCTION_REGISTRY.add(np, hash_numpy)


class NumpyExternallyCachedValue(ExternallyCachedValue):
    def load(self):
        return np.load(self.path, "r")


class NumpyCacheHandler(ModuleCacheHandler):

    def get_estimated_size(self, value) -> int:
        if isinstance(value, np_types):
            return value.nbytes

        return sys.getsizeof(value)

    def cache(self, value, external_path_builder: ExternallyCachedFilePathBuilder) -> CachedValue:
        if external_path_builder is not None:
            shape_info = '_'.join(tuple(value.shape))
            external_path = external_path_builder.build(shape_info, "npy")

            np.save(external_path, value)

            return NumpyExternallyCachedValue(external_path)


CACHED_VALUE_REGISTRY.add(np, NumpyCacheHandler())


def wrap_numpy_value(value):
    if isinstance(value, np_types):
        # We also make value readonly.
        value.setflags(write=False)
        return value.view()
    return None


RETURN_HANDLER_REGISTRY.add(np, wrap_numpy_value)
