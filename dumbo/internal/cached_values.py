import os
from abc import ABC
from dataclasses import dataclass, replace
from typing import Optional, NoReturn


class CachedValue:
    """Wraps a value that is being cached offline."""

    def unlink(self) -> NoReturn:
        # This value is about to not be part of the cache anymore.
        # Deal with it (by removing auxiliary files etc).
        pass

    def load(self):
        raise NotImplementedError()

    def get_stored_size(self) -> int:
        raise NotImplementedError()


@dataclass
class ExternallyCachedFilePath:
    """Builder for file paths for externally cached values."""

    path: str
    external_id: str
    vid_info: str

    @staticmethod
    def for_tuple_item(path: "Optional[ExternallyCachedFilePath]", i: int) -> "Optional[ExternallyCachedFilePath]":
        if path is None:
            return None

        return replace(path, external_id=path.external_id + f"_{i}")

    def build(self, cache_info, ext):
        return os.path.join(self.path, f"{self.vid_info}_{cache_info}_{self.external_id}.{ext}")


@dataclass
class ExternallyCachedValue(CachedValue, ABC):
    """A value that is cached with external resources."""

    path: str

    def unlink(self):
        unlinked_path = self.path + ".unlinked"
        # TODO: shall we pass the vid as argument and store it in a file next to
        # the unlinked entry?
        os.rename(self.path, unlinked_path)

    def get_stored_size(self):
        return os.path.getsize(self.path)


