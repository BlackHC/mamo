import torch as th
from typing import Optional

import hashlib

from dumbo.api_support import DBCachedValue, ExternallyCachedValue, ModuleExtension, \
    ExternallyCachedFilePath, CachedValue, MODULE_EXTENSIONS


# TODO: does this all work for cuda tensors????


class TorchExternallyCachedValue(ExternallyCachedValue):
    def load(self):
        return th.load(self.path)


class TorchModuleExtension(ModuleExtension):
    def supports(self, value) -> bool:
        return isinstance(value, th.Tensor)

    def compute_fingerprint(self, value: th.Tensor):
        return hashlib.md5(value.numpy()).digest()

    def get_estimated_size(self, value: th.Tensor) -> Optional[int]:
        return value.numel() * value.element_size()

    def cache_value(self, value: th.Tensor, external_path_builder: Optional[ExternallyCachedFilePath]) -> Optional[
        CachedValue]:
        if external_path_builder is None:
            return DBCachedValue(value)

        shape_info = '_'.join(map(str, value.shape))
        external_path = external_path_builder.build(shape_info, "pth")

        th.save(value, external_path)

        return TorchExternallyCachedValue(external_path)

    def wrap_return_value(self, value: th.Tensor):
        return value.view(value.size())


MODULE_EXTENSIONS.add(th, TorchModuleExtension())
