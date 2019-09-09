from typing import Optional

import numpy as np
import hashlib

from dumbo.api_support import (
    DBCachedValue,
    ExternallyCachedValue,
    MAX_FINGERPRINT_LENGTH,
    ModuleExtension,
    ExternallyCachedFilePath,
    CachedValue,
    MODULE_EXTENSIONS,
)

np_types = (np.ndarray, np.record, np.matrix, np.recarray, np.chararray, np.generic, np.memmap)


class NumpyExternallyCachedValue(ExternallyCachedValue):
    def load(self):
        return np.load(self.path, "r")


class NumpyModuleExtension(ModuleExtension):
    def supports(self, value) -> bool:
        return isinstance(value, np_types)

    def compute_fingerprint(self, value):
        return hashlib.md5(value).digest()

    def get_estimated_size(self, value) -> Optional[int]:
        return value.nbytes

    def cache_value(self, value, external_path_builder: Optional[ExternallyCachedFilePath]) -> Optional[CachedValue]:
        if external_path_builder is None:
            return DBCachedValue(value)

        shape_info = "_".join(map(str, value.shape))
        external_path = external_path_builder.build(shape_info, "npy")

        np.save(external_path, value)

        return NumpyExternallyCachedValue(external_path)

    def wrap_return_value(self, value):
        # We also make value readonly.
        value.setflags(write=False)
        return value.view()


MODULE_EXTENSIONS.add(np, NumpyModuleExtension())
