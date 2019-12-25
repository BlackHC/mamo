from dataclasses import dataclass
from types import CodeType, FunctionType
from typing import Tuple, FrozenSet, Optional, Generic, TypeVar, Set, Dict, List
from weakref import WeakKeyDictionary

from dumbo.internal import reflection
from dumbo.internal.module_extension import MODULE_EXTENSIONS
from dumbo.internal.reflection import FunctionDependencies

T = TypeVar("T")


class Fingerprint:
    pass


@dataclass(frozen=True)
class FingerprintDigest(Fingerprint):
    digest: object


@dataclass(frozen=True)
class FingerprintDigestValue(FingerprintDigest):
    """`FingerprintDigest` that carries its original value to be more informative.

    For all purposes, we ignore the actual value for hashing and use the provided digest."""
    value: object

    def __eq__(self, other):
        return super().__eq__(other)

    def __hash__(self):
        return super().__hash__()


# We keep this separate from FunctionIdentity, so as to cache by identity
# and determine staleness using fingerprints.
# (Otherwise, we lack a key to index with and find stale entries.)
@dataclass(frozen=True)
class FunctionFingerprint(Fingerprint):
    fingerprint: object


# Includes dependencies.
@dataclass(frozen=True)
class DeepFunctionFingerprint(FunctionFingerprint):
    global_loads: FrozenSet[Tuple[Tuple[str, ...], Fingerprint]]
    func_calls: FrozenSet[Tuple[Tuple[str, ...], FunctionFingerprint]]


@dataclass(frozen=True)
class CallFingerprint(Fingerprint):
    function: FunctionFingerprint
    # Need fingerprints everywhere! This needs to be a separate hierarchy!
    args: Tuple[Optional[Fingerprint], ...]
    kwargs: FrozenSet[Tuple[str, Optional[Fingerprint]]]


# TODO: This can be part of the default module extension! (or its own extension!!)
# We can define a FunctionCall wrapper and pass that through the module system to allow for customization!
class FingerprintFactory:
    # TODO: use weak dicts!
    cache: WeakKeyDictionary[object, Fingerprint]
    code_object_deps: WeakKeyDictionary[CodeType, FunctionDependencies]
    # If not None, allows for deep function fingerprinting.
    deep_fingerprint_source_prefix: Optional[str]
    deep_fingerprint_stack: Set[CodeType]

    def __init__(self, deep_fingerprint_source_prefix: Optional[str]):
        self.cache = WeakKeyDictionary()
        self.code_object_deps = WeakKeyDictionary()

        self.deep_fingerprint_source_prefix = deep_fingerprint_source_prefix
        self.deep_fingerprint_stack = set()

    def register_fingerprint(self, value, fingerprint: Fingerprint):
        self.cache[value] = fingerprint

    def fingerprint_but_not_deep(self, value):
        if value in self.cache:
            return self.cache[value]

        if isinstance(value, FunctionType):
            return self._get_function_fingerprint(value, allow_deep=False)
        return self._fingerprint_value(value)

    def fingerprint_function(self, func):
        # Function fingerprints (when we allow deep fingerprints) cannot be cached
        return self._get_function_fingerprint(func)

    def fingerprint_call(self, func: FunctionType, args: List, kwargs: Dict):
        # Call fingerprints (when we allow deep fingerprints) cannot be cached
        func_fingerprint = self._get_function_fingerprint(func)
        args_fingerprints = tuple(self.fingerprint_but_not_deep(arg) for arg in args)
        kwargs_fingerprints = frozenset((name, self.fingerprint_but_not_deep(arg)) for name, arg in kwargs.items())

        return CallFingerprint(func_fingerprint, args_fingerprints, kwargs_fingerprints)

    def _fingerprint_value(self, value):
        fingerprint = None
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

        return fingerprint

    def _get_code_object_deps(self, code_object) -> FunctionDependencies:
        code_object_deps = self.code_object_deps.get(code_object)
        if code_object_deps is None:
            code_object_deps = reflection.get_func_deps(code_object)
            self.code_object_deps[code_object] = code_object_deps
        return code_object_deps

    def _get_deep_fingerprint(self, code_object, namespace):
        # TODO: Could walk the tree and collect globals, calls etc one time only and then resolve them!
        if code_object in self.deep_fingerprint_stack:
            return FunctionFingerprint(reflection.get_code_object_fingerprint(code_object))
        self.deep_fingerprint_stack.add(code_object)
        try:
            # TODO: need a cache for this (also to catch recursion!!!)
            func_deps = self._get_code_object_deps(code_object)

            resolved_globals = reflection.resolve_qualified_names(func_deps.global_loads, namespace)
            resolved_funcs = reflection.resolve_qualified_names(func_deps.func_calls, namespace)

            global_vids = {
                qn: self.fingerprint_but_not_deep(resolved_global)
                for qn, resolved_global in resolved_globals.items()
            }
            global_funcs = {
                qn: self._get_function_fingerprint(resolved_func)
                for qn, resolved_func in resolved_funcs.items()
            }

            return DeepFunctionFingerprint(
                reflection.get_code_object_fingerprint(code_object),
                frozenset(global_vids.items()),
                frozenset(global_funcs.items()),
            )
        finally:
            self.deep_fingerprint_stack.remove(code_object)

    def _get_function_fingerprint(self, func: FunctionType, allow_deep=True) -> Optional[FunctionFingerprint]:
        if reflection.is_func_builtin(func):
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
