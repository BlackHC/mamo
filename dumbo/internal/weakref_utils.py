import weakref
from typing import Dict, Iterator, TypeVar, Generic
from typing import MutableMapping
import objproxies


KT = TypeVar("KT")  # Key type.
VT = TypeVar("VT")  # Value type.


def supports_weakrefs(value):
    return type(value).__weakrefoffset__ != 0


class ObjectProxy(objproxies.ObjectProxy):
    __slots__ = ("__weakref__",)


class IdMapFinalizer(Generic[KT]):
    id_to_finalizer: Dict[int, weakref.finalize]

    def __init__(self):
        self.id_to_finalizer = {}

    def _finalizer(self, id_value, custom_handler):
        del self.id_to_finalizer[id_value]
        custom_handler(id_value)

    def lookup_id(self, id_value):
        return self.id_to_finalizer[id_value].peek()[0]

    def register(self, value: KT, custom_handler):
        if not supports_weakrefs(value):
            # TODO: log?
            return

        id_value = id(value)
        if id_value in self.id_to_finalizer:
            raise ValueError(f"{value} has already been added to the finalizer!")

        self.id_to_finalizer[id_value] = weakref.finalize(value, self._finalizer, id_value, custom_handler)

    def release(self, value: KT):
        id_value = id(value)
        finalizer = self.id_to_finalizer.get(id_value)
        if finalizer is not None:
            finalizer.detach()
            del self.id_to_finalizer[id_value]

    def clear(self):
        for finalizer in self.id_to_finalizer.values():
            finalizer.detach()
        self.id_to_finalizer.clear()

    def __del__(self):
        self.clear()


class WeakKeyIdMap(MutableMapping[KT, VT]):
    id_map_to_value: Dict[int, VT]
    id_map_finalizer: IdMapFinalizer

    def __init__(self):
        self.id_map_to_value = {}
        self.id_map_finalizer = IdMapFinalizer()

    def _release(self, id_value):
        del self.id_map_to_value[id_value]

    def __setitem__(self, k: KT, v: VT) -> None:
        id_k = id(k)
        if id_k not in self.id_map_to_value:
            self.id_map_finalizer.register(k, self._release)
        self.id_map_to_value[id_k] = v

    def __delitem__(self, k: KT) -> None:
        del self.id_map_to_value[id(k)]
        self.id_map_finalizer.release(k)

    def __getitem__(self, k: KT) -> VT:
        return self.id_map_to_value[id(k)]

    def __len__(self) -> int:
        return len(self.id_map_to_value)

    def __iter__(self) -> Iterator[KT]:
        return map(self.id_map_finalizer.lookup_id, self.id_map_to_value)
