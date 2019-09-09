import os
from abc import ABC
from dataclasses import dataclass, replace
from typing import Optional


class CachedValue:
    def unlink(self):
        # This value is about to not be part of the cache anymore.
        # Deal with it (by removing auxiliary files etc).
        pass

    def load(self):
        raise NotImplementedError()


@dataclass
class ExternallyCachedFilePath:
    path: str
    external_id: str
    vid_info: str

    @staticmethod
    def for_tuple_item(path: "Optional[ExternallyCachedFilePath]", i: int):
        if path is None:
            return None

        return replace(path, external_id=path.external_id + f"_{i}")

    def build(self, cache_info, ext):
        return os.path.join(self.path, f"{self.vid_info}_{cache_info}_{self.external_id}.{ext}")


@dataclass(unsafe_hash=True)
class ExternallyCachedValue(CachedValue, ABC):
    path: str

    def unlink(self):
        unlinked_path = self.path + ".unlinked"
        # TODO: shall we pass the vid as argument and store it in a file next to
        # the unlinked entry?
        os.rename(self.path, unlinked_path)


@dataclass(unsafe_hash=True)
class DBCachedValue(CachedValue, ABC):
    cached_value: object

    def load(self):
        return self.cached_value
