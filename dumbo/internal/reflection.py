import hashlib
from typing import Dict, Callable, TypeVar, Generic
from dataclasses import dataclass, field


T = TypeVar("T")


@dataclass
class ModuleRegistry(Generic[T]):
    default_value: T = None
    store: Dict[str, T] = field(default_factory=dict, init=False)

    def add(self, module, handler):
        self.store[module.__name__] = handler

    def get(self, value) -> T:
        module_name = get_module_name(value)
        handler = self.store.get(module_name, self.default_value)
        return handler


def get_module_name(value):
    return value.__class__.__module__


def get_qualified_name(func):
    # TODO: handle Jupyter notebooks?
    # In notebooks, __module__ will be "__main__".
    return f"{func.__module__}.{func.__qualname__}"


def get_type_qualified_name(value):
    return get_qualified_name(type(value))


def get_func_qualified_name(func):
    return get_qualified_name(func)


def get_func_hash(func):
    return hashlib.md5(func.__code__.co_code).digest()


FINGERPRINT_FUNCTION_REGISTRY: ModuleRegistry[Callable] = ModuleRegistry(default_value=None)


def try_get_value_fingerprint(value):
    # TODO: support more types... seriously
    if isinstance(value, (bool, int, float, str,)):
        return value

    hashed_value = None

    hash_function = FINGERPRINT_FUNCTION_REGISTRY.get(value)
    if hash_function is not None:
        hashed_value = hash_function(value)

    return hashed_value
