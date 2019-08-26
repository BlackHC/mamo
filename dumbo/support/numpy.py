import numpy as np
import hashlib
from dumbo.internal.reflection import HASH_FUNCTION_REGISTRY
from dumbo.internal.persisted_cache import ModuleCacheHandler, ExternallyCachedValue, CACHED_VALUE_REGISTRY, ExternallyCachedFilePathBuilder, \
    CachedValue


def hash_numpy(value):
    if isinstance(value, np.ndarray):
        return hashlib.md5(value).digest()

    # TODO: log that we don't support a specific type?
    return None


HASH_FUNCTION_REGISTRY.add(np, hash_numpy)


class NumpyExternallyCachedValue(ExternallyCachedValue):
    def load(self):
        return np.load(self.path, "r")


class NumpyCacheHandler(ModuleCacheHandler):

    def get_estimated_size(self, value) -> int:
        return value.nbytes

    def cache(self, value, external_path_builder: ExternallyCachedFilePathBuilder) -> CachedValue:
        if external_path_builder is not None:
            shape_info = '_'.tuple(value.shape)
            external_path = external_path_builder.build(shape_info, "npy")

            np.save(external_path, value)

            return NumpyExternallyCachedValue(external_path)


CACHED_VALUE_REGISTRY.add(np, NumpyCacheHandler())
