from dataclasses import dataclass, field
from typing import Optional, Dict, TypeVar

from dumbo.internal.cached_values import ExternallyCachedFilePath, CachedValue
from dumbo.internal.reflection import get_module_name


MAX_FINGERPRINT_LENGTH = 1024


@dataclass
class ModuleExtension:
    module_registry: 'ModuleRegistry' = None

    def supports(self, value) -> bool:
        raise NotImplementedError()

    def compute_fingerprint(self, value):
        """Returns None if the fingerprint couldn't be created."""
        raise NotImplementedError()

    def get_estimated_size(self, value) -> Optional[int]:
        """Returns None if the size couldn't be estimated."""
        raise NotImplementedError()

    def cache_value(self, value, external_path_builder: Optional[ExternallyCachedFilePath]) -> Optional[CachedValue]:
        """Returns None if the value couldn't be cached."""
        raise NotImplementedError()

    def wrap_return_value(self, value):
        """Returns None if the value couldn't be wrapped."""
        raise NotImplementedError()


T = TypeVar("T")


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

    def supports(self, value) -> bool:
        extension = self.get(value)
        value_supported = None
        if extension is not None:
            value_supported = extension.supports(value)
        if value_supported is None:
            value_supported = self.default_extension.supports(value)
        return value_supported

    def compute_fingerprint(self, value):
        extension = self.get(value)
        fingerprint = None
        if extension is not None and extension.supports(value):
            fingerprint = extension.compute_fingerprint(value)
        if fingerprint is None:
            fingerprint = self.default_extension.compute_fingerprint(value)
        return fingerprint

    def get_estimated_size(self, value) -> Optional[int]:
        extension = self.get(value)
        estimated_size = None
        if extension is not None and extension.supports(value):
            estimated_size = extension.get_estimated_size(value)

        if estimated_size is None:
            estimated_size = self.default_extension.get_estimated_size(value)
        return estimated_size

    def cache_value(self, value, external_path_builder: Optional[ExternallyCachedFilePath]) -> Optional[
        CachedValue]:
        extension = self.get(value)
        cached_value = None
        if extension is not None and extension.supports(value):
            cached_value = extension.cache_value(value, external_path_builder)

        if cached_value is None:
            cached_value = self.default_extension.cache_value(value, external_path_builder)
        return cached_value

    def wrap_return_value(self, value):
        # We cannot really do anything about None sadly.
        # Why?
        # Because we usually test for None using 'is\is not None'
        # and having a proxy breaks that.
        # The general rule is that one should not dumbo 'None' results

        # TODO: raise or log?
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
