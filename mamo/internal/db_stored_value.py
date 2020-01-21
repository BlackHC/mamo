import pickle
from dataclasses import dataclass
from typing import Optional

from mamo.internal.cached_values import CachedValue
from mamo.internal.module_extension import ObjectSaver


@dataclass(frozen=True)
class DBPickledValue(CachedValue):
    """A value that is cached in the database."""

    data: bytes

    @staticmethod
    def cache_value(value) -> Optional[CachedValue]:
        data = try_pickle(value)
        if data is None:
            return None
        return DBPickledValue(data)

    def load(self):
        return try_unpickle(self.data)

    def get_stored_size(self):
        return len(self.data)


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
