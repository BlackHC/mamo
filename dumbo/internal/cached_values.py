import os
import pickle
from abc import ABC
from dataclasses import dataclass, replace
from typing import Optional


class CachedValue:
    """Wraps a value that is being cached offline."""

    def unlink(self):
        # This value is about to not be part of the cache anymore.
        # Deal with it (by removing auxiliary files etc).
        pass

    def load(self):
        raise NotImplementedError()


@dataclass
class ExternallyCachedFilePath:
    """Builder for file paths for externally cached values."""

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


@dataclass
class ExternallyCachedValue(CachedValue, ABC):
    """A value that is cached with external resources."""

    path: str

    def unlink(self):
        unlinked_path = self.path + ".unlinked"
        # TODO: shall we pass the vid as argument and store it in a file next to
        # the unlinked entry?
        os.rename(self.path, unlinked_path)


@dataclass
class DBPickledValue(CachedValue):
    """A value that is cached in the database."""

    data: bytes

    def __init__(self, value):
        self.data = try_pickle(value)

    def load(self):
        return try_unpickle(self.data)


def try_pickle(value):
    try:
        return pickle.dumps(value)
    except pickle.PickleError as err:
        # TODO: log err
        print(err)
        return None


def try_unpickle(data: bytes):
    try:
        return pickle.loads(data)
    except pickle.PickleError as err:
        # TODO: log err
        print(err)
        return None
