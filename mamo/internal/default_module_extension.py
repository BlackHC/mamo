import pickle
from dataclasses import dataclass

from mamo.internal.weakref_utils import ObjectProxy

from typing import Optional, Tuple

from mamo.internal.cached_values import ExternallyCachedFilePath, CachedValue, ExternallyCachedValue
from mamo.internal.db_stored_value import DBPickledValue
from mamo.internal.module_extension import ModuleExtension, ObjectSaver

import hashlib

from mamo.internal.reflection import get_type_qualified_name

MAX_PICKLE_SIZE = 2 ** 30


@dataclass
class CachedTuple(CachedValue):
    values: Tuple[CachedValue, ...]

    def load(self):
        return tuple(item.load() for item in self.values)

    def unlink(self):
        for item in self.values:
            item.unlink()

    def get_stored_size(self) -> int:
        return sum(item.get_stored_size() for item in self.values)


class DefaultTupleObjectSaver(ObjectSaver):
    def __init__(self, value, object_savers: Tuple[ObjectSaver]):
        super().__init__(value)
        self.object_savers = object_savers

    def get_estimated_size(self) -> int:
        return sum(object_saver.get_estimated_size() for object_saver in self.object_savers)

    def compute_digest_(self):
        hash_method = hashlib.md5()
        for object_saver in self.object_savers:
            hash_method.update(object_saver.compute_digest())
        return hash_method.digest()

    def cache_value(self, external_path_builder: Optional[ExternallyCachedFilePath]) -> Optional[CachedValue]:
        cached_items = tuple(
            object_saver.cache_value(ExternallyCachedFilePath.for_tuple_item(external_path_builder, i))
            for i, object_saver in enumerate(self.object_savers))
        if any(item is None for item in cached_items):
            return None
        return CachedTuple(cached_items)


class DefaultExternallyCachedValue(ExternallyCachedValue):

    def load(self):
        with open(self.path, "br") as external_file:
            pickled_bytes = external_file.read()

        try:
            return pickle.loads(pickled_bytes)
        except pickle.PickleError as err:
            # TODO: log err
            print(err)
            return None

    @staticmethod
    def save(external_path, pickled_bytes):
        # TODO: add error handling!
        with open(external_path, "bw") as external_file:
            external_file.write(pickled_bytes)

        return DefaultExternallyCachedValue(external_path)


class DefaultObjectSaver(ObjectSaver):
    def __init__(self, value, pickled_bytes):
        super().__init__(value)
        self.pickled_bytes = pickled_bytes

    def get_estimated_size(self) -> Optional[int]:
        return len(self.pickled_bytes)

    def compute_digest_(self):
        return hashlib.md5(self.pickled_bytes).digest()

    def cache_value(self, external_path_builder: Optional[ExternallyCachedFilePath]) -> Optional[CachedValue]:
        if external_path_builder is not None:
            external_path = external_path_builder.build(get_type_qualified_name(self.value), "pickle")
            cached_value = DefaultExternallyCachedValue.save(external_path, self.pickled_bytes)
        else:
            cached_value = DBPickledValue(self.pickled_bytes)

        # TODO: catch transactions error for objects that cannot be pickled here?
        return cached_value


class DefaultModuleExtension(ModuleExtension):
    def supports(self, value):
        return True

    def get_object_saver(self, value) -> Optional[ObjectSaver]:
        if isinstance(value, tuple):
            return DefaultTupleObjectSaver(value, tuple(self.module_registry.get_object_saver(item) for item in value))

        try:
            pickled_bytes = pickle.dumps(value)
        except pickle.PicklingError as err:
            # TODO: log err
            print(err)
            return None

        if len(pickled_bytes) > MAX_PICKLE_SIZE:
            # TODO: log
            return None

        return DefaultObjectSaver(value, pickled_bytes)

    def wrap_return_value(self, value):
        # Treat tuples different for functions returning multiple values.
        # We usually want to wrap them separately.
        if isinstance(value, tuple):
            return tuple(self.module_registry.wrap_return_value(item) for item in value)

        if not isinstance(value, ObjectProxy):
            return ObjectProxy(value)

        # If the value is already wrapped, create a new proxy.
        # This is necessary so that if we pass the same object through nested mamo functions
        # the result doesn't share identities (which is important for staleness!)
        return ObjectProxy(value.__subject__)
