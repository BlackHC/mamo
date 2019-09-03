from types import FunctionType
from typing import Optional, Dict

from dumbo.internal import reflection
from functools import wraps

# Usually, Pythonistas don't like base classes. They know nothing.
from dumbo.internal.identities import ValueNameIdentity, ValueFingerprintIdentity, ValueCIDIdentity, FunctionIdentity, \
    CallIdentity, ValueIdentity, FunctionFingerprint, DeepFunctionFingerprint, StoredResult, StoredValue
from dumbo.internal.module_extension import MODULE_EXTENSIONS
from dumbo.internal.online_cache import DumboOnlineCache
from dumbo.internal.persisted_cache import DumboPersistedCache

from dumbo.internal import default_module_extension

# Install the default module extension.
from dumbo.internal.reflection import FunctionDependencies

MODULE_EXTENSIONS.default_extension = default_module_extension.DefaultModuleExtension()


class Dumbo:
    # TODO: use weak dicts!
    func_deps: Dict[FunctionType, FunctionDependencies]
    # TODO: make use of this dict!!
    #vids_deps: Dict[object, ValueIdentity]
    func_fingerprints: Dict[FunctionType, FunctionFingerprint]

    online_cache: DumboOnlineCache
    persisted_cache: DumboPersistedCache

    def __init__(self, persisted_cache):
        self.persisted_cache = persisted_cache
        self.online_cache = DumboOnlineCache(persisted_cache)
        self.func_deps = {}
        self.func_fingerprints = {}

    def _get_stored_value(self, vid):
        return self.online_cache.get_stored_value(vid)

    def _get_vid(self, value):
        return self.online_cache.get_vid(value)

    def _identify_function(self, func) -> FunctionIdentity:
        return FunctionIdentity(
            reflection.get_func_qualified_name(func),
        )

    def _get_func_deps(self, func) -> FunctionDependencies:
        func_deps = self.func_deps.get(func)
        if func_deps is None:
            func_deps = reflection.get_func_deps(func)
            self.func_deps[func] = func_deps
        return func_deps

    def _get_function_fingerprint(self, func) -> Optional[FunctionFingerprint]:
        func_fingerprint = self.func_fingerprints.get(func)
        if func_fingerprint is not None:
            return func_fingerprint

        if reflection.is_func_builtin(func):
            func_fingerprint = None
        # TODO: allow to set a localprefix
        elif reflection.is_func_local(func, ''):
            func_deps = self._get_func_deps(func)

            resolved_globals = reflection.resolve_qualified_names(func_deps.global_loads)
            resolved_funcs = reflection.resolve_qualified_names(func_deps.func_calls)

            global_vids = {qn: self._identify_value(resolved_global) if resolved_global else None for
                           qn, resolved_global in resolved_globals.items()}
            global_funcs = {qn: self._identify_function(resolved_func) if resolved_func else None for
                            qn, resolved_func in resolved_funcs.items()}

            func_fingerprint = DeepFunctionFingerprint(
                reflection.get_func_fingerprint(func),
                frozenset(global_vids.items()),
                frozenset(global_funcs.items()))
        else:
            func_fingerprint = FunctionFingerprint(reflection.get_func_fingerprint(func))

        self.func_fingerprints[func] = func_fingerprint
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
            raise ValueError(f'Cannot fingerprint {value}!'
                             ' Please either add an extension to support it,'
                             ' or register it with a name')

        return ValueFingerprintIdentity(
            reflection.get_type_qualified_name(value),
            fingerprint
        )

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
                    print(f'{cid} is stale!'
                          f'\t{func_fingerprint}\nvs\n\t{memoized_result.func_fingerprint}')
                return memoized_result.value

            result = func(*args, **kwargs)
            wrapped_result = MODULE_EXTENSIONS.wrap_return_value(result)
            dumbo.online_cache.update(vid, StoredResult(wrapped_result, func_fingerprint))
            return wrapped_result

        return wrapped_func

    def register_external_value(self, unique_name, value):
        # TODO: add an error here if value already exists within the cache.
        self.online_cache.update(ValueNameIdentity(unique_name), StoredValue(value))

    def tag(self, tag_name, value):
        # Value should exist in the cache.
        if value is not None:
            if not self.online_cache.has_value(value):
                raise ValueError('Value has not been registered previously!')
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


def init_dumbo(memory_only=True, path=None):
    global dumbo
    assert dumbo is None

    persisted_cache = DumboPersistedCache.from_memory() if memory_only else DumboPersistedCache.from_file(path)
    dumbo = Dumbo(persisted_cache)
