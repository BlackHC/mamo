import torch as th
import hashlib
from dumbo.internal.reflection import HASH_FUNCTION_REGISTRY
from dumbo.internal.persisted_cache import ModuleCacheHandler, ExternallyCachedValue, CACHED_VALUE_REGISTRY, ExternallyCachedFilePathBuilder, \
    CachedValue
from dumbo.internal.return_handlers import RETURN_HANDLER_REGISTRY

# TODO: does this all work for cuda tensors????

def hash_torch(value):
    # We don't bother to fingerprint anything in PyTorch.
    # The tensors are likely to be big.
    return hashlib.md5(value).digest()


HASH_FUNCTION_REGISTRY.add(th, hash_torch)


class TorchExternallyCachedValue(ExternallyCachedValue):
    def load(self):
        return th.load(self.path)


class TorchCacheHandler(ModuleCacheHandler):

    def get_estimated_size(self, value) -> int:
        if isinstance(value, th.Tensor):
            return value.numel() * value.element_size()
        # TODO: fix this? support this!
        return None

    def cache(self, value, external_path_builder: ExternallyCachedFilePathBuilder) -> CachedValue:
        if external_path_builder is not None:
            shape_info = '_'.join(tuple(value.shape))
            external_path = external_path_builder.build(shape_info, "npy")

            th.save(external_path, value)

            return TorchExternallyCachedValue(external_path)


CACHED_VALUE_REGISTRY.add(th, TorchCacheHandler())


def wrap_torch_value(value):
    if isinstance(value, th.Tensor):
        return value.view(value.size())
    return None


RETURN_HANDLER_REGISTRY.add(th, wrap_torch_value)