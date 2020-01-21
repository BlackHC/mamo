import os
from typing import Optional

import numpy as np
import hashlib

from mamo.api_support import (
    DBPickledValue,
    ExternallyCachedValue,
    ModuleExtension,
    ObjectSaver,
    ExternallyCachedFilePath,
    CachedValue,
    MODULE_EXTENSIONS,
)

np_types = (np.ndarray, np.record, np.matrix, np.recarray, np.chararray, np.generic, np.memmap)


class NumpyExternallyCachedValue(ExternallyCachedValue):
    def load(self):
        return np.load(self.path, "r")

    @staticmethod
    def save(external_path, value):
        np.save(external_path, value)

        return NumpyExternallyCachedValue(external_path)


class NumpyObjectSaver(ObjectSaver):
    def __init__(self, value):
        super().__init__(value)
        self.value = value

    def get_estimated_size(self) -> Optional[int]:
        return self.value.nbytes

    def compute_digest_(self):
        return hashlib.md5(self.value).digest()

    def cache_value(self, external_path_builder: Optional[ExternallyCachedFilePath]) -> Optional[CachedValue]:
        if external_path_builder is None:
            return DBPickledValue.cache_value(self.value)

        shape_info = "_".join(map(str, self.value.shape))
        external_path = external_path_builder.build(shape_info, "npy")

        return NumpyExternallyCachedValue.save(external_path, self.value)


class NumpyModuleExtension(ModuleExtension):
    def supports(self, value) -> bool:
        return isinstance(value, np_types)

    def get_object_saver(self, value) -> Optional[ObjectSaver]:
        return NumpyObjectSaver(value)

    def wrap_return_value(self, value):
        # We also make value readonly.
        value.setflags(write=False)
        return value.view()


MODULE_EXTENSIONS.add(np, NumpyModuleExtension())
