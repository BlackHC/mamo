import inspect
from types import CodeType, FunctionType
from typing import Optional, Set, Dict, MutableMapping
from weakref import WeakKeyDictionary

from mamo.internal import reflection
from mamo.internal.fingerprints import (
    FunctionFingerprint,
    DeepFunctionFingerprint,
    CallFingerprint,
    FingerprintDigestRepr,
    CellResultFingerprint,
    CellFingerprint,
    Fingerprint, MAX_FINGERPRINT_VALUE_LENGTH)
from mamo.internal.identities import (
    ValueCallIdentity,
    ComputedValueIdentity,
    ValueIdentityVisitor,
    ValueCellResultIdentity)
from mamo.internal.module_extension import MODULE_EXTENSIONS
from mamo.internal.providers import ValueProvider, FunctionProvider, FingerprintProvider, ValueOracle
from mamo.internal.reflection import FunctionDependencies

# TODO: This can be part of the default module extension! (or its own extension!!)
# We can define a FunctionCall wrapper and pass that through the module system to allow for customization!
from mamo.internal.weakref_utils import WeakKeyIdMap


class FingerprintRegistry(FingerprintProvider):
    # TODO: We only need the FingerprintProvider bit of ValueProvider!
    # Once we move
    value_provider: ValueProvider
    value_oracle: ValueOracle
    function_provider: FunctionProvider

    cache: WeakKeyIdMap[object, Fingerprint]

    # actually a WeakKeyDictionary!
    code_object_deps: MutableMapping[CodeType, FunctionDependencies]
    # If not None, allows for deep function fingerprinting.
    deep_fingerprint_source_prefix: Optional[str]
    deep_fingerprint_stack: Set[CodeType]

    def __init__(
            self,
            deep_fingerprint_source_prefix: Optional[str],
            value_provider: ValueProvider,
            value_oracle: ValueOracle,
            function_provider: FunctionProvider
    ):
        self.cache = WeakKeyIdMap()

        self.code_object_deps = WeakKeyDictionary()

        self.deep_fingerprint_source_prefix = deep_fingerprint_source_prefix
        self.deep_fingerprint_stack = set()

        self.value_provider = value_provider
        self.value_oracle = value_oracle
        self.function_provider = function_provider

    def fingerprint_value(self, value):
        # TODO: do I want to store strings like that?
        if value is None or isinstance(value, (bool, int, float)) or (isinstance(value, str) and len(value) <
                                                                      MAX_FINGERPRINT_VALUE_LENGTH):
            # TODO: special-case strings and summarize them?
            return FingerprintDigestRepr(value, repr(value))

        fingerprint = self.cache.get(value)
        if fingerprint is not None:
            return fingerprint

        # TODO: this is a special case of a computing a digest!?
        if isinstance(value, FunctionType):
            fingerprint = FingerprintDigestRepr(self._get_function_fingerprint(value, allow_deep=False),
                                                reflection.get_func_qualified_name(value))
        else:
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

    def fingerprint_call(self, func: FunctionType, args, kwargs: Dict):
        # Call fingerprints (when we allow deep fingerprints) cannot be cached
        func_fingerprint = self._get_function_fingerprint(func)
        args_fingerprints = tuple(self.value_oracle.fingerprint_value(arg) for arg in args)
        kwargs_fingerprints = frozenset((name, self.value_oracle.fingerprint_value(arg)) for name, arg in kwargs.items())

        return CallFingerprint(func_fingerprint, args_fingerprints, kwargs_fingerprints)

    def fingerprint_cell(self, cell_function: FunctionType) -> CellFingerprint:
        cell_code_fingerprint = self._get_deep_fingerprint(cell_function.__code__, cell_function.__globals__)

        func_deps = reflection.get_func_deps(cell_function)
        global_loads = func_deps.global_loads
        global_stores = func_deps.global_stores

        resolved_globals_loads = reflection.resolve_qualified_names(global_loads, cell_function.__globals__)
        globals_load_fingerprint = frozenset(
            (name, (self.value_oracle.identify_value(value), self.value_oracle.fingerprint_value(value)))
            for name, value in resolved_globals_loads.items()
        )
        cell_fingerprint = CellFingerprint(cell_code_fingerprint, globals_load_fingerprint, frozenset(global_stores))
        return cell_fingerprint

    def fingerprint_cell_result(self, cell_fingerprint: CellFingerprint, key: str):
        return CellResultFingerprint(cell_fingerprint, key)

    def fingerprint_computed_value(self, vid: ComputedValueIdentity):
        # TODO: move back to main.py:is_stale_vid!
        outer_self = self

        class Visitor(ValueIdentityVisitor):
            def visit_call(self, vid: ValueCallIdentity):
                func_fingerprint = outer_self.fingerprint_function(
                    outer_self.function_provider.resolve_function(vid.fid)
                )
                arg_fingerprints = [
                    outer_self.value_provider.resolve_fingerprint(arg_vid) for arg_vid in vid.args_vid
                ]
                kwarg_fingerprints = [
                    (name, outer_self.value_provider.resolve_fingerprint(arg_vid))
                    for name, arg_vid in vid.kwargs_vid
                ]
                return CallFingerprint(func_fingerprint, tuple(arg_fingerprints), frozenset(kwarg_fingerprints))

            def visit_cell_result(self, vid: ValueCellResultIdentity):
                cell_function = outer_self.function_provider.resolve_function(vid.cell)
                return outer_self.fingerprint_cell_result(outer_self.fingerprint_cell(cell_function), vid.key)

        return Visitor().visit(vid)

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

            # TODO: this does not seem to resolve builtins!!?!?! debug

            global_funcs = {
                qn: self._get_function_fingerprint(resolved_func, allow_deep=True)
                for qn, resolved_func in resolved_funcs.items() if resolved_func
            }

            return DeepFunctionFingerprint(
                reflection.get_code_object_fingerprint(code_object), frozenset(global_funcs.items())
            )
        finally:
            self.deep_fingerprint_stack.remove(code_object)

    def _get_function_fingerprint(self, callee, allow_deep=True) -> Optional[FunctionFingerprint]:
        # TODO: necessary?
        if callee is None:
            return None
        elif reflection.is_func_builtin(callee):
            func_fingerprint = FunctionFingerprint(callee.__qualname__)
        else:
            # TODO: more tests? code review?
            if isinstance(callee, FunctionType):
                func = callee
            else:
                assert callable(callee), callee
                # Needs tests!
                if isinstance(callee, type):
                    sub_callable = callee.__init__
                elif hasattr(callee, '__func__'):
                    sub_callable = callee.__func__
                elif hasattr(callee, '__call__'):
                    sub_callable = callee.__call__
                else:
                    # log and fail softly?
                    raise NotImplementedError(f'Missing support for fingerprinting callable {callee}!')
                return self._get_function_fingerprint(sub_callable, allow_deep=allow_deep)

            if not hasattr(callee, '__code__') or not hasattr(callee, '__globals__'):
                import types
                isbuiltin = inspect.isbuiltin(callee)

            # Unwrap special functions.
            if hasattr(callee, "mamo_unwrapped_func"):
                callee = callee.mamo_unwrapped_func

            if allow_deep and reflection.is_func_local(callee, self.deep_fingerprint_source_prefix):
                func_fingerprint = self._get_deep_fingerprint(callee.__code__, callee.__globals__)
            else:
                func_fingerprint = FunctionFingerprint(reflection.get_func_fingerprint(callee))

        return func_fingerprint
