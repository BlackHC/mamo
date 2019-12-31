import ast
from typing import Optional

from functools import wraps

from dumbo.internal.fingerprint_factory import FingerprintFactory
from dumbo.internal.fingerprints import FingerprintProvider, Fingerprint, CellResultFingerprint
from dumbo.internal.identities import (
    FunctionIdentity,
    ValueIdentity,
    StoredResult,
    StoredValue,
    IdentityProvider,
    value_name_identity,
    ComputedValueIdentity,
    ValueCallIdentity,
    ValueCellResultIdentity,
)
from dumbo.internal.identity_registry import IdentityRegistry
from dumbo.internal.module_extension import MODULE_EXTENSIONS
from dumbo.internal.online_cache import DumboOnlineCache
from dumbo.internal.persisted_cache import DumboPersistedCache

from dumbo.internal import default_module_extension

# Install the default module extension.
MODULE_EXTENSIONS.set_default_extension(default_module_extension.DefaultModuleExtension())


class ReExecutionPolicy:
    def __call__(
            self,
            dumbo: "Dumbo",
            vid: ComputedValueIdentity,
            fingerprint: Fingerprint,
            stored_fingerprint: Optional[Fingerprint],
    ):
        return True


def execute_decision_only_missing(
        dumbo: "Dumbo", vid: ComputedValueIdentity, fingerprint: Fingerprint, stored_fingerprint: Optional[Fingerprint]
):
    return False


def execute_decision_stale(max_depth):
    def decider(
            dumbo: "Dumbo", vid: ComputedValueIdentity, fingerprint: Fingerprint,
            stored_fingerprint: Optional[Fingerprint]
    ):
        if fingerprint != stored_fingerprint:
            return True
        return dumbo.is_stale_vid(vid, depth=max_depth)

    return decider


class Dumbo(IdentityProvider, FingerprintProvider):
    fingerprint_factory: FingerprintFactory

    identity_registry: IdentityRegistry
    online_cache: DumboOnlineCache

    persisted_cache: DumboPersistedCache

    re_execution_policy: ReExecutionPolicy

    def __init__(self, persisted_cache, deep_fingerprint_source_prefix: Optional[str],
                 re_execution_policy: Optional[ReExecutionPolicy]):
        self.persisted_cache = persisted_cache
        self.online_cache = DumboOnlineCache(persisted_cache)

        self.fingerprint_factory = FingerprintFactory(deep_fingerprint_source_prefix, self.online_cache, self)
        self.identity_registry = IdentityRegistry(self.online_cache, self)

        self.re_execution_policy = re_execution_policy or execute_decision_stale(-1)

    def identify_value(self, value):
        return self.identity_registry.identify_value(value)

    def fingerprint_value(self, value):
        return self.fingerprint_factory.fingerprint_value(value)

    def resolve_function(self, fid: FunctionIdentity):
        return self.identity_registry.resolve_function(fid)

    @property
    def deep_fingerprint_source_prefix(self):
        return self.fingerprint_factory.deep_fingerprint_source_prefix

    # TODO: remove this property again (only used by tests!)

    @deep_fingerprint_source_prefix.setter
    def deep_fingerprint_source_prefix(self, value):
        self.fingerprint_factory.deep_fingerprint_source_prefix = value

    def _get_stored_value(self, vid):
        return self.online_cache.get_stored_value(vid)

    def _get_vid(self, value):
        return self.online_cache.get_vid(value)

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

    def is_stale_call(self, func, args, kwargs, *, depth=-1):
        fid = self.identity_registry.identify_function(func)
        vid = self.identity_registry.identify_call(fid, args, kwargs)

        return self.is_stale_vid(vid, depth=depth)

    def is_stale(self, value, *, depth):
        if self.online_cache.is_stale(value):
            return True

        vid = self._get_vid(value)
        if vid is None:
            # TODO: throw?
            return True

        return self.is_stale_vid(vid, depth=depth)

    def is_stale_vid(self, vid: Optional[ValueIdentity], *, depth):
        if vid is None:
            return False
        if not isinstance(vid, ComputedValueIdentity):
            return False

        fingerprint = self.fingerprint_factory.fingerprint_computed_value(vid)
        stored_fingerprint = self.online_cache.get_stored_fingerprint(vid)

        if fingerprint != stored_fingerprint:
            return True

        if depth == 0:
            return False

        if isinstance(vid, ValueCallIdentity):
            return any(self.is_stale_vid(arg_vid, depth=depth - 1) for arg_vid in vid.args_vid) or any(
                self.is_stale_vid(arg_vid, depth=depth - 1) for name, arg_vid in vid.kwargs_vid
            )
        elif isinstance(vid, ValueCellResultIdentity):
            assert isinstance(fingerprint, CellResultFingerprint)
            return any(
                self.is_stale_vid(input_vid, depth=depth - 1)
                for name, (input_vid, input_fingerprint) in fingerprint.cell.globals_load
            )

    def is_cached(self, func, args, kwargs):
        fid = self.identity_registry.identify_function(func)
        vid = self.identity_registry.identify_call(fid, args, kwargs)

        return self.online_cache.has_vid(vid)

    def forget_call(self, func, args, kwargs):
        fid = self.identity_registry.identify_function(func)
        vid = self.identity_registry.identify_call(fid, args, kwargs)

        self.online_cache.update(vid, None)

    def forget(self, value):
        vid = self._get_vid(value)
        if vid is None:
            # TODO: throw or log
            return
        self.online_cache.update(vid, None)

    def _shall_execute(self, vid, fingerprint):
        stored_fingerprint = dumbo.online_cache.get_stored_fingerprint(vid)
        return stored_fingerprint is None or self.re_execution_policy(self, vid, fingerprint, stored_fingerprint)

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

                fid = dumbo.identity_registry.identify_function(func)

            vid = dumbo.identity_registry.identify_call(fid, args, kwargs)

            call_fingerprint = dumbo.fingerprint_factory.fingerprint_call(func, args, kwargs)

            if dumbo._shall_execute(vid, call_fingerprint):
                result = func(*args, **kwargs)
                wrapped_result = MODULE_EXTENSIONS.wrap_return_value(result)
                dumbo.online_cache.update(vid, StoredResult(wrapped_result, call_fingerprint))

                return wrapped_result

            cached_result = dumbo._get_stored_value(vid)
            if cached_result is None:
                # log?
                raise RuntimeError(f"Couldn't find cached result for {vid}!")

            return cached_result.value

        wrapped_func.dumbo_unwrapped_func = func
        wrapped_func.is_stale = lambda *args, **kwargs: dumbo.is_stale_call(func, args, kwargs)
        wrapped_func.is_cached = lambda *args, **kwargs: dumbo.is_cached(func, args, kwargs)
        wrapped_func.forget = lambda *args, **kwargs: dumbo.forget_call(func, args, kwargs)

        # This method is a static method, so that dumbo does not need to be initialized.
        fid = None
        if dumbo is not None:
            fid = dumbo.identity_registry.identify_function(func)

        return wrapped_func

    def run_cell(self, name: Optional[str], cell: str, user_ns: dict):
        # TODO: wrap in a function and execute, so we need explicit globals for stores?
        function_module = ast.parse("def cell_function():\n  pass")
        cell_module = ast.parse(cell)
        function_module.body[0].body = cell_module.body
        compiled_function = compile(function_module, "cell", "exec")

        local_ns = {}
        exec(compiled_function, user_ns, local_ns)
        cell_function = local_ns["cell_function"]
        code_object = cell_function.__code__

        cell_id = self.identity_registry.identify_cell(name, cell_function)
        cell_fingerprint = self.fingerprint_factory.fingerprint_cell(cell_function)

        outputs = cell_fingerprint.outputs

        result_vids = {name: self.identity_registry.identify_cell_result(cell_id, name) for name in outputs}
        result_fingerprints = {
            name: self.fingerprint_factory.fingerprint_cell_result(cell_fingerprint, name) for name in outputs
        }

        # TODO: this adds some staleness overhead but not sure how to handle composites atm.
        if any(dumbo._shall_execute(result_vids[name], result_fingerprints[name]) for name in outputs):
            cell_function()

            # Retrieve stores.
            wrapped_results = {name: MODULE_EXTENSIONS.wrap_return_value(user_ns[name]) for name in outputs}
            user_ns.update(wrapped_results)

            for name in outputs:
                dumbo.online_cache.update(result_vids[name], StoredResult(user_ns[name], result_fingerprints[name]))
        else:
            for name in outputs:
                vid = result_vids[name]
                cached_result = dumbo._get_stored_value(vid)
                if cached_result is None:
                    # log?
                    raise RuntimeError(f"Couldn't find cached result for {vid}!")

                assert isinstance(cached_result, StoredResult)
                user_ns[name] = cached_result.value

    def register_external_value(self, unique_name, value):
        # TODO: add an error here if value already exists within the cache.
        vid = value_name_identity(unique_name)
        self.online_cache.update(vid, StoredValue(value, vid.fingerprint))

        # TODO: add a test!

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
        stored_value = self._get_stored_value(value_name_identity(unique_name))
        if stored_value is None:
            return None
        return stored_value.value

    def testing_close(self):
        self.persisted_cache.testing_close()
        self.identity_registry = None
        self.fingerprint_factory = None
        import gc
        gc.collect()


dumbo: Optional[Dumbo] = None


def init_dumbo(
        memory_only=True,
        path: Optional[str] = None,
        externally_cached_path: Optional[str] = None,
        # By default, we don't use deep fingerprints except in the main module/jupyter notebooks.
        deep_fingerprint_source_prefix: Optional[str] = None,
        re_execution_policy: Optional[ReExecutionPolicy] = None
):
    global dumbo
    assert dumbo is None

    persisted_cache = (
        DumboPersistedCache.from_memory()
        if memory_only
        else DumboPersistedCache.from_file(path, externally_cached_path)
    )
    dumbo = Dumbo(persisted_cache, deep_fingerprint_source_prefix, re_execution_policy)
