import os
from typing import Optional

import numpy as np
import hashlib

from dumbo.api_support import (
    ExternallyCachedValue,
    ModuleExtension,
    ObjectSaver,
    ExternallyCachedFilePath,
    CachedValue,
    MODULE_EXTENSIONS,
)
from dumbo.internal.db_stored_value import DBPickledValue

np_types = (np.ndarray, np.record, np.matrix, np.recarray, np.chararray, np.generic, np.memmap)


class NumpyExternallyCachedValue(ExternallyCachedValue):
    def load(self):
        return np.load(self.path, "r")


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

        np.save(external_path, self.value)

        return NumpyExternallyCachedValue(external_path)


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
