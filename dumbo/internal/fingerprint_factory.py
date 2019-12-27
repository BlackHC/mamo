from types import CodeType, FunctionType
from typing import Optional, Set, Dict, MutableMapping, Any
from weakref import WeakKeyDictionary

from dumbo.internal import reflection
from dumbo.internal.fingerprints import (
    FunctionFingerprint,
    DeepFunctionFingerprint,
    CallFingerprint,
    FingerprintDigestValue,
    FingerprintProvider,
)
from dumbo.internal.identities import IdentityProvider, ValueFingerprintIdentity, ValueCallIdentity
from dumbo.internal.module_extension import MODULE_EXTENSIONS
from dumbo.internal.online_cache import DumboOnlineCache
from dumbo.internal.reflection import FunctionDependencies


# TODO: This can be part of the default module extension! (or its own extension!!)
# We can define a FunctionCall wrapper and pass that through the module system to allow for customization!
from dumbo.internal.weakref_utils import WeakKeyIdMap


class FingerprintFactory(FingerprintProvider):
    online_cache: DumboOnlineCache
    identity_provider: IdentityProvider

    cache: WeakKeyIdMap[Any, FingerprintDigestValue]

    # actually a WeakKeyDictionary!
    code_object_deps: MutableMapping[CodeType, FunctionDependencies]
    # If not None, allows for deep function fingerprinting.
    deep_fingerprint_source_prefix: Optional[str]
    deep_fingerprint_stack: Set[CodeType]

    def __init__(
        self,
        deep_fingerprint_source_prefix: Optional[str],
        online_cache: DumboOnlineCache,
        identity_provider: IdentityProvider,
    ):
        self.online_cache = online_cache
        self.identity_provider = identity_provider

        self.cache = WeakKeyIdMap()

        self.code_object_deps = WeakKeyDictionary()

        self.deep_fingerprint_source_prefix = deep_fingerprint_source_prefix
        self.deep_fingerprint_stack = set()

    def fingerprint_value(self, value):
        # TODO: do I want to store strings like that?
        if value is None or isinstance(value, (bool, int, float, str)):
            return FingerprintDigestValue(value, value)

        fingerprint = None

        if isinstance(value, FunctionType):
            fingerprint = self._get_function_fingerprint(value, allow_deep=False)
        else:
            vid = self.online_cache.get_vid(value)
            if vid is not None:
                if isinstance(vid, ValueFingerprintIdentity):
                    fingerprint = vid.fingerprint
                else:
                    fingerprint = self.online_cache.get_fingerprint_from_vid(vid)

            # Don't try to cache values that are part of online_cache.
            if fingerprint is not None:
                return fingerprint

        if fingerprint is None:
            fingerprint = self.cache.get(value)

        if fingerprint is None:
            object_saver = MODULE_EXTENSIONS.get_object_saver(value)
            if object_saver is not None:
                fingerprint = object_saver.compute_fingerprint()

        if fingerprint is None:
            # TODO: log?
            raise ValueError(
                f"Cannot fingerprint {value}!"
                " Please either add an extension to support it,"
                " or register it with a name"
            )

        self.cache[value] = fingerprint

        return fingerprint

    def fingerprint_function(self, func):
        # Function fingerprints (when we allow deep fingerprints) cannot be cached
        return self._get_function_fingerprint(func, allow_deep=True)

    def fingerprint_cell_code(self, cell_code, namespace):
        # Function fingerprints (when we allow deep fingerprints) cannot be cached
        return self._get_deep_fingerprint(cell_code, namespace)

    def fingerprint_call(self, func: FunctionType, args, kwargs: Dict):
        # Call fingerprints (when we allow deep fingerprints) cannot be cached
        func_fingerprint = self._get_function_fingerprint(func)
        args_fingerprints = tuple(self.fingerprint_value(arg) for arg in args)
        kwargs_fingerprints = frozenset((name, self.fingerprint_value(arg)) for name, arg in kwargs.items())

        return CallFingerprint(func_fingerprint, args_fingerprints, kwargs_fingerprints)

    def fingerprint_call_vid(self, vid: ValueCallIdentity):
        func_fingerprint = self.identity_provider.resolve_function(vid.fid)
        arg_fingerprints = [self.online_cache.get_fingerprint_from_vid(arg_vid) for arg_vid in vid.args_vid]
        kwarg_fingerprints = [
            (name, self.online_cache.get_fingerprint_from_vid(arg_vid)) for name, arg_vid in vid.kwargs_vid
        ]
        return CallFingerprint(func_fingerprint, tuple(arg_fingerprints), frozenset(kwarg_fingerprints))

    def _get_code_object_deps(self, code_object) -> FunctionDependencies:
        code_object_deps = self.code_object_deps.get(code_object)
        if code_object_deps is None:
            code_object_deps = reflection.get_func_deps(code_object)
            self.code_object_deps[code_object] = code_object_deps
        return code_object_deps

    def _get_deep_fingerprint(self, code_object, namespace):
        if code_object in self.deep_fingerprint_stack:
            return FunctionFingerprint(reflection.get_code_object_fingerprint(code_object))
        self.deep_fingerprint_stack.add(code_object)
        try:
            func_deps = self._get_code_object_deps(code_object)

            resolved_funcs = reflection.resolve_qualified_names(func_deps.func_calls, namespace)

            global_funcs = {
                qn: self._get_function_fingerprint(resolved_func, allow_deep=True)
                for qn, resolved_func in resolved_funcs.items()
            }

            return DeepFunctionFingerprint(
                reflection.get_code_object_fingerprint(code_object), frozenset(global_funcs.items())
            )
        finally:
            self.deep_fingerprint_stack.remove(code_object)

    def _get_function_fingerprint(self, func: FunctionType, allow_deep=True) -> Optional[FunctionFingerprint]:
        if func is None:
            func_fingerprint = FunctionFingerprint(None)
        elif reflection.is_func_builtin(func):
            func_fingerprint = FunctionFingerprint(func.__qualname__)
        else:
            # Unwrap special functions.
            if hasattr(func, "dumbo_unwrapped_func"):
                func = func.dumbo_unwrapped_func

            if allow_deep and reflection.is_func_local(func, self.deep_fingerprint_source_prefix):
                func_fingerprint = self._get_deep_fingerprint(func.__code__, func.__globals__)
            else:
                func_fingerprint = FunctionFingerprint(reflection.get_func_fingerprint(func))

        return func_fingerprint
