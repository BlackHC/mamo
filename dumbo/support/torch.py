import torch as th
from typing import Optional

import hashlib

from dumbo.api_support import (
    DBPickledValue,
    ExternallyCachedValue,
    ModuleExtension,
    ObjectSaver,
    ExternallyCachedFilePath,
    CachedValue,
    MODULE_EXTENSIONS,
)


# TODO: does this all work for cuda tensors????


class TorchExternallyCachedValue(ExternallyCachedValue):
    def load(self):
        return th.load(self.path)


class TorchObjectSaver(ObjectSaver):
    def __init__(self, value: th.Tensor):
        super().__init__(value)
        self.value = value

    def get_estimated_size(self) -> Optional[int]:
        return self.value.numel() * self.value.element_size()

    def compute_digest_(self):
        return hashlib.md5(self.value.numpy()).digest()

    def cache_value(self, external_path_builder: Optional[ExternallyCachedFilePath]) -> Optional[CachedValue]:
        if external_path_builder is None:
            return DBPickledValue(self.value)

        shape_info = "_".join(map(str, self.value.shape))
        external_path = external_path_builder.build(shape_info, "pth")

        th.save(self.value, external_path)

        return TorchExternallyCachedValue(external_path)


class TorchModuleExtension(ModuleExtension):
    def supports(self, value) -> bool:
        return isinstance(value, th.Tensor)

    def get_object_saver(self, value) -> Optional[ObjectSaver]:
        return TorchObjectSaver(value)

    def wrap_return_value(self, value: th.Tensor):
        return value.view(value.size())


MODULE_EXTENSIONS.add(th, TorchModuleExtension())
