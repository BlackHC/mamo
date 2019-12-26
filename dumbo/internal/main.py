import ast
from types import FunctionType, CodeType
from typing import Optional, Dict, Set

from dumbo.internal import reflection
from functools import wraps

from dumbo.internal.fingerprint_factory import FingerprintFactory
from dumbo.internal.identities import (
    ValueNameIdentity,
    ValueFingerprintIdentity,
    ValueCIDIdentity,
    FunctionIdentity,
    CallIdentity,
    ValueIdentity,
    StoredResult,
    StoredValue,
    CellIdentity,
    CallFingerprint)
from dumbo.internal.module_extension import MODULE_EXTENSIONS
from dumbo.internal.online_cache import DumboOnlineCache
from dumbo.internal.persisted_cache import DumboPersistedCache

from dumbo.internal import default_module_extension\


# Install the default module extension.
MODULE_EXTENSIONS.set_default_extension(default_module_extension.DefaultModuleExtension())


class Dumbo:
    # TODO: use weak dicts!
    fingerprint_factory: FingerprintFactory
    fid_to_func: Dict[FunctionIdentity, FunctionType]

    online_cache: DumboOnlineCache
    persisted_cache: DumboPersistedCache

    def __init__(self, persisted_cache, deep_fingerprint_source_prefix: Optional[str]):
        self.persisted_cache = persisted_cache
        self.online_cache = DumboOnlineCache(persisted_cache)

        self.fingerprint_factory = FingerprintFactory(deep_fingerprint_source_prefix)

        self.fid_to_func = {}

    @property
    def deep_fingerprint_source_prefix(self):
        return self.fingerprint_factory.deep_fingerprint_source_prefix

    @deep_fingerprint_source_prefix.setter
    def deep_fingerprint_source_prefix(self, value):
        self.fingerprint_factory.deep_fingerprint_source_prefix = value

    def _get_stored_value(self, vid):
        return self.online_cache.get_stored_result(vid)

    def _get_vid(self, value):
        return self.online_cache.get_vid(value)

    def _identify_function(self, func) -> FunctionIdentity:
        return FunctionIdentity(reflection.get_func_qualified_name(func))

    def _identify_cell(self, name: str, code_object: CodeType) -> FunctionIdentity:
        if name is not None:
            return CellIdentity(name, None)
        return CellIdentity(name, reflection.get_code_object_fingerprint(code_object))

    def _identify_call(self, fid, args, kwargs) -> CallIdentity:
        args_vid = tuple(self._identify_value(arg) for arg in args)
        kwargs_vid = frozenset((name, self._identify_value(value)) for name, value in kwargs.items())

        return CallIdentity(fid, args_vid, kwargs_vid)

    def _identify_value(self, value) -> ValueIdentity:
        vid = self._get_vid(value)
        if vid is not None:
            return vid

        fingerprint = self.fingerprint_factory.fingerprint_but_not_deep(value)

        return ValueFingerprintIdentity(reflection.get_type_qualified_name(value), fingerprint)

    def get_value_identities(self, persisted=False):
        # TODO: add tests
        # TODO: don't leak internal objects (convert to dicts or similar instead?)
        if not persisted:
            return self.online_cache.get_vids()

        vids = set()
        vids.update(self.persisted_cache.get_cached_vids())
        vids.update(self.online_cache.get_vids())
        return vids

    def flush_online_cache(self):
        self.online_cache.flush()

    def is_stale_call(self, func, args, kwargs):
        fid = self._identify_function(func)
        cid = self._identify_call(fid, args, kwargs)
        vid = ValueCIDIdentity(cid)

        call_fingerprint = self.fingerprint_factory.fingerprint_call(func, args, kwargs)
        stored_call_fingerprint = self.online_cache.get_call_fingerprint(vid)

        return call_fingerprint != stored_call_fingerprint

    # TODO: this one is less easy
    # def is_stale(self, value, *, depth):
    #     if self.online_cache.is_stale(value):
    #         return True
    #
    #     vid = self._get_vid(value)
    #     if vid is None:
    #         # TODO: throw instead!
    #         return True
    #     if not isinstance(vid, ValueCIDIdentity):
    #         return False
    #
    #     call_fingerprint = dumbo._get_call_fingerprint(vid, depth=depth)
    #     stored_call_fingerprint = dumbo.online_cache.get_call_fingerprint(vid)
    #
    #     return call_fingerprint != stored_call_fingerprint

    def is_cached(self, func, args, kwargs):
        fid = self._identify_function(func)
        cid = self._identify_call(fid, args, kwargs)
        vid = ValueCIDIdentity(cid)

        return self.online_cache.has_vid(vid)

    def forget_call(self, func, args, kwargs):
        fid = dumbo._identify_function(func)
        cid = dumbo._identify_call(fid, args, kwargs)
        vid = ValueCIDIdentity(cid)

        self.online_cache.update(vid, None)

    def forget(self, value):
        vid = self._get_vid(value)
        if vid is None:
            # TODO: throw or log
            return
        self.online_cache.update(vid, None)

    @staticmethod
    def wrap_function(func):
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
                dumbo.fid_to_func[fid] = wrapped_func

            cid = dumbo._identify_call(fid, args, kwargs)
            vid = ValueCIDIdentity(cid)

            call_fingerprint = dumbo.fingerprint_factory.fingerprint_call(func, args, kwargs)

            # TODO: could simplify logic by always fetching values using a method call.

            # TODO: logic about whether to load from cache or recompute!
            memoized_result = dumbo._get_stored_value(vid)
            if memoized_result is not None:
                assert isinstance(memoized_result, StoredResult)
                if call_fingerprint != memoized_result.call_fingerprint:
                    # TODO: log
                    print(f"{vid.cid} is stale!"
                          f"\t{call_fingerprint}\nvs\n\t{memoized_result.call_fingerprint}")
                return memoized_result.value

            result = func(*args, **kwargs)
            wrapped_result = MODULE_EXTENSIONS.wrap_return_value(result)
            dumbo.online_cache.update(vid, StoredResult(wrapped_result, call_fingerprint))

            return wrapped_result

        wrapped_func.dumbo_unwrapped_func = func
        wrapped_func.is_stale = lambda *args, **kwargs: dumbo.is_stale_call(func, args, kwargs)
        wrapped_func.is_cached = lambda *args, **kwargs: dumbo.is_cached(func, args, kwargs)
        wrapped_func.forget = lambda *args, **kwargs: dumbo.forget_call(func, args, kwargs)

        # This method is a static method, so that dumbo does not need to be initialized.
        fid = None
        if dumbo is not None:
            fid = dumbo._identify_function(func)
            dumbo.fid_to_func[fid] = wrapped_func

        return wrapped_func

    def run_cell(self,  name: Optional[str], cell: str, user_ns: dict):
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

        cell_id = self._identify_cell(name, code_object)

        loads, global_stores = reflection.get_global_loads_stores(code_object)

        cid = self._identify_call(cell_id, (), reflection.resolve_qualified_names(loads, user_ns))
        vid = ValueCIDIdentity(cid)

        # TODO: there is a lot of code shared between wrapped_func and run_cell!
        # TODO: These fingerprints are not cached! Do we want to cache them?
        cell_fingerprint = self.fingerprint_factory.fingerprint_cell_code(code_object, user_ns)
        call_fingerprint = CallFingerprint(cell_fingerprint, (), frozenset())

        # TODO: logic about whether to load from cache or recompute!
        memoized_result = dumbo._get_stored_value(vid)
        if memoized_result is not None:
            assert isinstance(memoized_result, StoredResult)
            if call_fingerprint != memoized_result.call_fingerprint:
                # TODO: log
                print(f"{vid.cid} is stale!" f"\t{call_fingerprint}\nvs\n\t{memoized_result.call_fingerprint}")
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

            dumbo.online_cache.update(vid, StoredResult(wrapped_results, call_fingerprint))
            user_ns.update(zip(*wrapped_results))

    def register_external_value(self, unique_name, value):
        # TODO: add an error here if value already exists within the cache.
        self.online_cache.update(ValueNameIdentity(unique_name), StoredValue(value))
        return value

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
               # By default, we don't use deep fingerprints except in the main module/jupyter notebooks.
               deep_fingerprint_source_prefix: Optional[str] = None):
    global dumbo
    assert dumbo is None

    persisted_cache = (
        DumboPersistedCache.from_memory()
        if memory_only
        else DumboPersistedCache.from_file(path, externally_cached_path)
    )
    dumbo = Dumbo(persisted_cache, deep_fingerprint_source_prefix)
