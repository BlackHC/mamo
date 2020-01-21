from abc import ABC
from dataclasses import dataclass, field
from typing import Optional, Dict, TypeVar

from mamo.internal.cached_values import ExternallyCachedFilePath, CachedValue
from mamo.internal.fingerprints import FingerprintDigest, FingerprintDigestRepr, MAX_FINGERPRINT_VALUE_LENGTH
from mamo.internal.reflection import get_module_name


T = TypeVar("T")

MISSING_DIGEST = object()


class ObjectSaver(ABC):
    def __init__(self, value):
        self.value = value
        self.digest = MISSING_DIGEST

    def get_estimated_size(self) -> Optional[int]:
        """Returns None if the size couldn't be estimated."""
        raise NotImplementedError()

    def compute_digest_(self):
        """Returns None if the digest couldn't be created."""
        raise NotImplementedError()

    def compute_digest(self):
        if self.digest is MISSING_DIGEST:
            self.digest = self.compute_digest_()

        return self.digest

    def compute_fingerprint(self):
        """Returns None if the fingerprint couldn't be created."""
        digest = self.compute_digest()
        if digest is None:
            # TODO: log?
            return None

        estimated_size = self.get_estimated_size()
        if estimated_size is not None and estimated_size <= MAX_FINGERPRINT_VALUE_LENGTH:
            return FingerprintDigestRepr(digest, repr(self.value))
        return FingerprintDigest(digest)

    def cache_value(self, external_path_builder: Optional[ExternallyCachedFilePath]) -> Optional[CachedValue]:
        """Returns None if the value couldn't be cached."""
        raise NotImplementedError()


@dataclass
class ModuleExtension:
    module_registry: "ModuleRegistry" = None

    def supports(self, value) -> bool:
        raise NotImplementedError()

    def get_object_saver(self, value) -> Optional[ObjectSaver]:
        """Returns an `ObjectSaver` or None if it couldn't be created."""
        raise NotImplementedError()

    def wrap_return_value(self, value):
        """Returns None if the value couldn't be wrapped."""
        raise NotImplementedError()


@dataclass
class ModuleRegistry:
    default_extension: ModuleExtension = None
    store: Dict[str, ModuleExtension] = field(default_factory=dict, init=False)

    def set_default_extension(self, handler: ModuleExtension):
        self.default_extension = handler
        handler.module_registry = self

    def add(self, module, handler: ModuleExtension):
        self.store[module.__name__] = handler
        handler.module_registry = self

    def get(self, value) -> ModuleExtension:
        module_name = get_module_name(value)
        extension = self.store.get(module_name)
        return extension

    def get_object_saver(self, value) -> ObjectSaver:
        extension = self.get(value)
        object_saver = None
        if extension is not None and extension.supports(value):
            object_saver = extension.get_object_saver(value)

        if object_saver is None:
            object_saver = self.default_extension.get_object_saver(value)
        return object_saver

    def wrap_return_value(self, value):
        # We cannot really do anything about None sadly.
        # Why?
        # Because we usually test for None using 'is\is not None'
        # and having a proxy breaks that.
        # The general rule is that one should not mamo 'None' results

        # TODO: raise or log? (probably throw because it breaks staleness etc?)
        if value is None:
            return None

        extension = self.get(value)
        return_value = None
        if extension is not None and extension.supports(value):
            return_value = extension.wrap_return_value(value)

        if return_value is None:
            return_value = self.default_extension.wrap_return_value(value)

        if return_value is None:
            return_value = value

        return return_value


MODULE_EXTENSIONS = ModuleRegistry()
