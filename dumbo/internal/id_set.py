from typing import MutableSet, MutableMapping, TypeVar, Iterator, Dict, Tuple

T = TypeVar('T')
T_co = TypeVar('T_co', covariant=True)  # Any type covariant containers.


# TODO: add tests
class IdSet(MutableSet[T]):
    id_value: Dict[int, T]

    def __init__(self):
        self.id_value = {}

    def add(self, x: T) -> None:
        self.id_value[id(x)] = x

    def discard(self, x: T) -> None:
        if x in self:
            del self.id_value[id(x)]

    def clear(self) -> None:
        self.id_value.clear()

    def __contains__(self, x: object) -> bool:
        return id(x) in self.id_value

    def __len__(self) -> int:
        return len(self.id_value)

    def __iter__(self) -> Iterator[T_co]:
        return iter(self.id_value.values())


KT = TypeVar("KT")  # Key type.
VT = TypeVar("VT")  # Value type.
KT_co = TypeVar('KT_co', covariant=True)  # Value type covariant containers.
VT_co = TypeVar('VT_co', covariant=True)  # Value type covariant containers.


class KeyIdMap(MutableMapping[KT, VT]):
    id_key_value: Dict[int, Tuple[KT, VT]]

    def __init__(self):
        self.id_key_value = {}

    def __setitem__(self, k: KT, v: VT) -> None:
        self.id_key_value[id(k)] = (k, v)

    def __delitem__(self, k: KT) -> None:
        del self.id_key_value[id(k)]

    def __getitem__(self, k: KT) -> VT:
        return self.id_key_value[id(k)][1]

    def __len__(self) -> int:
        return len(self.id_key_value)

    def __iter__(self) -> Iterator[KT]:
        for key, value in self.id_key_value.values():
            yield value
