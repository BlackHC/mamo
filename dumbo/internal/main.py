import ast
from types import FunctionType, CodeType
from typing import Optional, Dict, Set

from dumbo.internal import reflection
from functools import wraps

# Usually, Pythonistas don't like base classes. They know nothing.
from dumbo.internal.identities import (
    ValueNameIdentity,
    ValueFingerprintIdentity,
    ValueCIDIdentity,
    FunctionIdentity,
    CallIdentity,
    ValueIdentity,
    FunctionFingerprint,
    DeepFunctionFingerprint,
    StoredResult,
    StoredValue,
    CellIdentity,
)
from dumbo.internal.module_extension import MODULE_EXTENSIONS
from dumbo.internal.online_cache import DumboOnlineCache
from dumbo.internal.persisted_cache import DumboPersistedCache

from dumbo.internal import default_module_extension

# Install the default module extension.
from dumbo.internal.reflection import FunctionDependencies

MODULE_EXTENSIONS.set_default_extension(default_module_extension.DefaultModuleExtension())


class Dumbo:
    # TODO: use weak dicts!
    code_object_deps: Dict[CodeType, FunctionDependencies]
    # TODO: make use of this dict!!
    # vids_deps: Dict[object, ValueIdentity]
    # If not None, allows for deep function fingerprinting.
    deep_fingerprint_source_prefix: Optional[str]
    deep_fingerprint_stack: Set[CodeType]

    online_cache: DumboOnlineCache
    persisted_cache: DumboPersistedCache

    def __init__(self, persisted_cache, deep_fingerprint_source_prefix: Optional[str]):
        self.persisted_cache = persisted_cache
        self.online_cache = DumboOnlineCache(persisted_cache)
        self.code_object_deps = {}
        self.deep_fingerprint_source_prefix = deep_fingerprint_source_prefix
        self.deep_fingerprint_stack = set()

    def _get_stored_value(self, vid):
        return self.online_cache.get_stored_value(vid)

    def _get_vid(self, value):
        return self.online_cache.get_vid(value)

    def _identify_function(self, func) -> FunctionIdentity:
        return FunctionIdentity(reflection.get_func_qualified_name(func))

    def _identify_cell(self, code_object: CodeType) -> FunctionIdentity:
        return CellIdentity("cell", reflection.get_code_object_fingerprint(code_object))

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
            # TODO: need a cache for this (also to catch recursion!!!)
            func_deps = self._get_code_object_deps(code_object)

            resolved_globals = reflection.resolve_qualified_names(func_deps.global_loads, namespace)
            resolved_funcs = reflection.resolve_qualified_names(func_deps.func_calls, namespace)

            global_vids = {
                qn: self._identify_value(resolved_global) if resolved_global else None
                for qn, resolved_global in resolved_globals.items()
            }
            global_funcs = {
                qn: (self._identify_function(resolved_func),
                     self._get_function_fingerprint(resolved_func)) if resolved_func else None
                for qn, resolved_func in resolved_funcs.items()
            }

            return DeepFunctionFingerprint(
                reflection.get_code_object_fingerprint(code_object),
                frozenset(global_vids.items()),
                frozenset(global_funcs.items()),
            )
        finally:
            self.deep_fingerprint_stack.remove(code_object)

    def _get_function_fingerprint(self, func: FunctionType) -> Optional[FunctionFingerprint]:
        if reflection.is_func_builtin(func):
            func_fingerprint = None
        else:
            if hasattr(func, "dumbo_unwrapped_func"):
                func = func.dumbo_unwrapped_func

            if self.deep_fingerprint_source_prefix is not None and \
                    reflection.is_func_local(func, self.deep_fingerprint_source_prefix):
                func_fingerprint = self._get_deep_fingerprint(func.__code__, func.__globals__)
            else:
                func_fingerprint = FunctionFingerprint(reflection.get_func_fingerprint(func))

        return func_fingerprint

    def _identify_call(self, fid, args, kwargs) -> CallIdentity:
        args_vid = tuple(self._identify_value(arg) for arg in args)
        kwargs_vid = frozenset((name, self._identify_value(value)) for name, value in kwargs.items())

        return CallIdentity(fid, args_vid, kwargs_vid)

    def _identify_value(self, value) -> ValueIdentity:
        vid = self._get_vid(value)
        if vid is not None:
            return vid

        fingerprint = MODULE_EXTENSIONS.compute_fingerprint(value)

        if fingerprint is None:
            raise ValueError(
                f"Cannot fingerprint {value}!"
                " Please either add an extension to support it,"
                " or register it with a name"
            )

        return ValueFingerprintIdentity(reflection.get_type_qualified_name(value), fingerprint)

    @staticmethod
    def wrap_function(func):
        # This method is a static method, so that dumbo does not need to be initialized.
        fid = dumbo._identify_function(func) if dumbo is not None else None

        @wraps(func)
        def wrapped_func(*args, **kwargs):
            nonlocal fid

            # If dumbo was not initialized before, we might still have to set fid.
            if fid is None:
                # Just initialize it with defaults.
                if dumbo is None:
                    # TODO: maybe log?
                    init_dumbo()

                fid = dumbo._identify_function(func)

            cid = dumbo._identify_call(fid, args, kwargs)
            vid = ValueCIDIdentity(cid)

            func_fingerprint = dumbo._get_function_fingerprint(func)

            # TODO: logic about whether to load from cache or recompute!
            memoized_result = dumbo._get_stored_value(vid)
            if memoized_result is not None:
                assert isinstance(memoized_result, StoredResult)
                if func_fingerprint != memoized_result.func_fingerprint:
                    # TODO: log
                    print(f"{vid.cid} is stale!" f"\t{func_fingerprint}\nvs\n\t{memoized_result.func_fingerprint}")
                return memoized_result.value

            result = func(*args, **kwargs)
            wrapped_result = MODULE_EXTENSIONS.wrap_return_value(result)
            dumbo.online_cache.update(vid, StoredResult(wrapped_result, func_fingerprint))
            return wrapped_result

        wrapped_func.dumbo_unwrapped_func = func
        return wrapped_func

    def run_cell(self, cell: str, user_ns: dict):
        # TODO: wrap in a function and execute, so we need explicit globals for stores?
        # TODO: this needs to support space-based indentation!
        function_module = ast.parse("def cell_function():\n  pass")
        cell_module = ast.parse(cell)
        function_module.body[0].body = cell_module.body
        compiled_function = compile(function_module, 'cell', 'exec')

        local_ns = {}
        exec(compiled_function, user_ns, local_ns)
        cell_function = local_ns["cell_function"]
        code_object = cell_function.__code__

        cell_id = self._identify_cell(code_object)

        loads, global_stores = reflection.get_global_loads_stores(code_object)

        cid = self._identify_call(cell_id, (), reflection.resolve_qualified_names(loads, user_ns))
        vid = ValueCIDIdentity(cid)

        # TODO: there is a lot of code shared between wrapped_func and run_cell!
        # TODO: These fingerprints are not cached! Do we want to cache them?
        cell_fingerprint = self._get_deep_fingerprint(code_object, user_ns)

        # TODO: logic about whether to load from cache or recompute!
        memoized_result = dumbo._get_stored_value(vid)
        if memoized_result is not None:
            assert isinstance(memoized_result, StoredResult)
            if cell_fingerprint != memoized_result.func_fingerprint:
                # TODO: log
                print(f"{vid.cid} is stale!" f"\t{cell_fingerprint}\nvs\n\t{memoized_result.func_fingerprint}")
            assert isinstance(memoized_result.value, tuple)
            user_ns.update(zip(*memoized_result.value))
        else:
            cell_function()

            # Retrieve stores.
            # TODO: Need to support nested results for this?!!!
            results = {name: user_ns[name] for name in global_stores}
            unzipped_results = tuple(zip(*results.items()))
            # This will take care of each value separately. (At least for wrapping!!)
            wrapped_results = MODULE_EXTENSIONS.wrap_return_value(unzipped_results)

            dumbo.online_cache.update(vid, StoredResult(wrapped_results, cell_fingerprint))
            user_ns.update(zip(*wrapped_results))

    def register_external_value(self, unique_name, value):
        # TODO: add an error here if value already exists within the cache.
        self.online_cache.update(ValueNameIdentity(unique_name), StoredValue(value))

    def tag(self, tag_name, value):
        # Value should exist in the cache.
        if value is not None:
            if not self.online_cache.has_value(value):
                raise ValueError("Value has not been registered previously!")
            # Register value
            self.online_cache.tag(tag_name, self._get_vid(value))
        else:
            self.online_cache.tag(tag_name, None)

    def get_tag_value(self, tag_name):
        stored_value = self.online_cache.get_tag_stored_value(tag_name)
        if stored_value is None:
            return None
        return stored_value.value

    def get_external_value(self, unique_name):
        stored_value = self._get_stored_value(ValueNameIdentity(unique_name))
        if stored_value is None:
            return None
        return stored_value.value

    def testing_close(self):
        self.persisted_cache.testing_close()


dumbo: Optional[Dumbo] = None


def init_dumbo(memory_only=True,
               path: Optional[str] = None,
               externally_cached_path: Optional[str] = None,
               # By default, we use deep fingerprints everywhere for now.
               deep_fingerprint_source_prefix: Optional[str] = ""):
    global dumbo
    assert dumbo is None

    persisted_cache = (
        DumboPersistedCache.from_memory()
        if memory_only
        else DumboPersistedCache.from_file(path, externally_cached_path)
    )
    dumbo = Dumbo(persisted_cache, deep_fingerprint_source_prefix)
