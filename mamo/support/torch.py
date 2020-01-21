import torch as th
from typing import Optional

import hashlib

from mamo.api_support import (
    ExternallyCachedValue,
    ModuleExtension,
    ObjectSaver,
    ExternallyCachedFilePath,
    CachedValue,
    DBPickledValue,
    MODULE_EXTENSIONS,
)


# TODO: does this all work for cuda tensors????


class TorchExternallyCachedValue(ExternallyCachedValue):
    def load(self):
        return th.load(self.path)

    @staticmethod
    def save(external_path, value):
        th.save(value, external_path)

        return TorchExternallyCachedValue(external_path)


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
            return DBPickledValue.cache_value(self.value)

        shape_info = "_".join(map(str, self.value.shape))
        external_path = external_path_builder.build(shape_info, "pth")

        return TorchExternallyCachedValue.save(external_path, self.value)


class TorchModuleExtension(ModuleExtension):
    def supports(self, value) -> bool:
        return isinstance(value, th.Tensor)

    def get_object_saver(self, value) -> Optional[ObjectSaver]:
        return TorchObjectSaver(value)

    def wrap_return_value(self, value: th.Tensor):
        return value.view(value.size())


MODULE_EXTENSIONS.add(th, TorchModuleExtension())
