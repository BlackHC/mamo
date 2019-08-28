import os
from abc import ABC
from dataclasses import dataclass

from persistent import Persistent


class CachedValue(Persistent):
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

    def build(self, cache_info, ext):
        return os.path.join(
            self.path,
            f'{self.vid_info}_{cache_info}_{self.external_id}.{ext}'
        )


@dataclass(unsafe_hash=True)
class ExternallyCachedValue(CachedValue, ABC):
    path: str

    def unlink(self):
        unlinked_path = self.path + '.unlinked'
        # TODO: shall we pass the vid as argument and store it in a file next to
        # the unlinked entry?
        os.rename(self.path, unlinked_path)


@dataclass(unsafe_hash=True)
class DBCachedValue(CachedValue, ABC):
    value: object

    def load(self):
        return self.value
