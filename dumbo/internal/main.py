import ast
from typing import Optional

from functools import wraps

from dumbo.internal.fingerprint_registry import FingerprintRegistry
from dumbo.internal.fingerprints import Fingerprint, CellResultFingerprint, ResultFingerprint
from dumbo.internal.identities import (
    FunctionIdentity,
    ValueIdentity,
    value_name_identity,
    ComputedValueIdentity,
    ValueCallIdentity,
    ValueCellResultIdentity)
from dumbo.internal.providers import IdentityProvider, FunctionProvider, FingerprintProvider
from dumbo.internal.annotated_value import AnnotatedValue
from dumbo.internal.identity_registry import IdentityRegistry
from dumbo.internal.function_registry import FunctionRegistry
from dumbo.internal.module_extension import MODULE_EXTENSIONS
from dumbo.internal.online_cache import OnlineLayer
from dumbo.internal.value_provider_mediator import ValueProviderMediator
from dumbo.internal.value_registries import ValueRegistry
from dumbo.internal.staleness_registry import StalenessRegistry
from dumbo.internal.persisted_cache import DumboPersistedCache

from dumbo.internal import default_module_extension

# Install the default module extension.
MODULE_EXTENSIONS.set_default_extension(default_module_extension.DefaultModuleExtension())


class ReExecutionPolicy:
    def __call__(
            self,
            dumbo: "Dumbo",
            vid: ComputedValueIdentity,
            fingerprint: ResultFingerprint,
            stored_fingerprint: Optional[ResultFingerprint],
    ):
        return True


def execute_decision_only_missing(
        dumbo: "Dumbo", vid: ComputedValueIdentity, fingerprint: Fingerprint, stored_fingerprint: Optional[Fingerprint]
):
    return False


def execute_decision_stale(max_depth):
    def decider(
            dumbo: "Dumbo", vid: ComputedValueIdentity, fingerprint: ResultFingerprint,
            stored_fingerprint: Optional[ResultFingerprint]
    ):
        if fingerprint != stored_fingerprint:
            return True
        return dumbo.is_stale_vid(vid, depth=max_depth)

    return decider


class Dumbo(IdentityProvider, FingerprintProvider):
    fingerprint_factory: FingerprintRegistry

    staleness_registry: StalenessRegistry
    identity_registry: IdentityRegistry
    function_registry: FunctionRegistry

    value_provider_mediator: ValueProviderMediator
    external_values: ValueRegistry
    online_layer: OnlineLayer

    persisted_cache: DumboPersistedCache

    re_execution_policy: ReExecutionPolicy

    def __init__(self, persisted_cache, deep_fingerprint_source_prefix: Optional[str],
                 re_execution_policy: Optional[ReExecutionPolicy]):
        self.persisted_cache = persisted_cache
        self.staleness_registry = StalenessRegistry()

        self.external_values = ValueRegistry(self.staleness_registry)
        self.online_layer = OnlineLayer(self.staleness_registry, persisted_cache)
        self.value_provider_mediator = ValueProviderMediator(self.online_layer, self.external_values)

        self.function_registry = FunctionRegistry()
        self.fingerprint_factory = FingerprintRegistry(deep_fingerprint_source_prefix, self.value_provider_mediator, self, self.function_registry)
        self.identity_registry = IdentityRegistry(self.value_provider_mediator, self)

        self.re_execution_policy = re_execution_policy or execute_decision_stale(-1)

    def identify_value(self, value):
        return self.identity_registry.identify_value(value)

    def fingerprint_value(self, value):
        return self.fingerprint_factory.fingerprint_value(value)

    @property
    def deep_fingerprint_source_prefix(self):
        return self.fingerprint_factory.deep_fingerprint_source_prefix

    # TODO: remove this property again (only used by tests!)

    @deep_fingerprint_source_prefix.setter
    def deep_fingerprint_source_prefix(self, value):
        self.fingerprint_factory.deep_fingerprint_source_prefix = value

    def _get_value(self, vid: ValueIdentity):
        return self.value_provider_mediator.resolve_value(vid)

    def _get_vid(self, value: object):
        return self.value_provider_mediator.identify_value(value)

    def get_value_identities(self, persisted=False):
        # TODO: optimize to always create a new set?
        vids = self.value_provider_mediator.get_vids()
        if persisted:
            vids.update(self.persisted_cache.get_vids())
        return vids

    def flush_cache(self):
        self.online_layer.flush()

    def is_stale_call(self, func, args, kwargs, *, depth=-1):
        fid = self.function_registry.identify_function(func)
        vid = self.identity_registry.identify_call(fid, args, kwargs)

        return self.is_stale_vid(vid, depth=depth)

    def is_stale(self, value, *, depth=-1):
        if self.staleness_registry.is_stale(value):
            # More interesting result type?!
            # Value has become stale!'
            return True

        vid = self._get_vid(value)
        if vid is None:
            # TODO: throw?
            print('Vid not found!')
            return True

        return self.is_stale_vid(vid, depth=depth)

    def is_stale_vid(self, vid: Optional[ValueIdentity], *, depth):
        if vid is None:
            return False
        if not isinstance(vid, ComputedValueIdentity):
            return False

        fingerprint = self.fingerprint_factory.fingerprint_computed_value(vid)
        stored_fingerprint = self.value_provider_mediator.resolve_fingerprint(vid)

        if fingerprint != stored_fingerprint:
            print(f'{vid} is stale!')
            print(f'{fingerprint}\nvs\n{stored_fingerprint}')
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
        fid = self.function_registry.identify_function(func)
        vid = self.identity_registry.identify_call(fid, args, kwargs)

        return self.value_provider_mediator.has_vid(vid)

    def forget_call(self, func, args, kwargs):
        fid = self.function_registry.identify_function(func)
        vid = self.identity_registry.identify_call(fid, args, kwargs)

        self.value_provider_mediator.register(vid, None, None)

    def forget(self, value):
        vid = self._get_vid(value)
        if vid is None:
            # TODO: throw or log
            return
        self.value_provider_mediator.register(vid, None, None)

    def _shall_execute(self, vid: ComputedValueIdentity, fingerprint: ResultFingerprint):
        # TODO: could directly ask persisted_cache
        stored_fingerprint = dumbo.online_layer.resolve_fingerprint(vid)
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

                fid = dumbo.function_registry.identify_function(func)

            vid = dumbo.identity_registry.identify_call(fid, args, kwargs)

            call_fingerprint = dumbo.fingerprint_factory.fingerprint_call(func, args, kwargs)

            if dumbo._shall_execute(vid, call_fingerprint):
                result = func(*args, **kwargs)
                wrapped_result = MODULE_EXTENSIONS.wrap_return_value(result)
                dumbo.online_layer.update(vid, AnnotatedValue(wrapped_result, call_fingerprint))

                return wrapped_result

            cached_result = dumbo._get_value(vid)
            if cached_result is None:
                # log?
                raise RuntimeError(f"Couldn't find cached result for {vid}!")

            return cached_result

        wrapped_func.dumbo_unwrapped_func = func
        wrapped_func.is_stale = lambda *args, **kwargs: dumbo.is_stale_call(func, args, kwargs)
        wrapped_func.is_cached = lambda *args, **kwargs: dumbo.is_cached(func, args, kwargs)
        wrapped_func.forget = lambda *args, **kwargs: dumbo.forget_call(func, args, kwargs)

        # This method is a static method, so that dumbo does not need to be initialized.
        fid = None
        if dumbo is not None:
            fid = dumbo.function_registry.identify_function(func)

        return wrapped_func

    def run_cell(self, name: Optional[str], cell_code: str, user_ns: dict):
        # TODO: wrap in a function and execute, so we need explicit globals for stores?
        function_module = ast.parse("def cell_function():\n  pass")
        cell_module = ast.parse(cell_code)
        function_module.body[0].body = cell_module.body
        compiled_function = compile(function_module, "cell", "exec")

        local_ns = {}
        exec(compiled_function, user_ns, local_ns)
        cell_function = local_ns["cell_function"]

        cell_id = self.function_registry.identify_cell(name, cell_function)
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
                dumbo.online_layer.update(result_vids[name], AnnotatedValue(user_ns[name], result_fingerprints[name]))
        else:
            for name in outputs:
                vid = result_vids[name]
                cached_result = dumbo._get_value(vid)
                if cached_result is None:
                    # log?
                    raise RuntimeError(f"Couldn't find cached result for {vid}!")

                user_ns[name] = cached_result

    def tag(self, tag_name: str, value: Optional[object]):
        vid = None
        # Value should exist in the cache.
        if value is not None:
            vid = self.value_provider_mediator.identify_value(value)
            if vid is None:
                raise ValueError("Value has not been registered previously!")

        self.persisted_cache.tag(tag_name, vid)

    def get_tag_value(self, tag_name):
        # TODO: might have to expose has_tag etc?
        vid = self.persisted_cache.get_tag_vid(tag_name)
        if vid is None:
            # TODO: log instead
            #raise ValueError(f"{tag_name} has not been registered previously!")
            return None
        value = self.value_provider_mediator.resolve_value(vid)
        if value is None:
            # TODO: log instead!
            #raise ValueError(f"{vid} for {tag_name} is not available anymore!")
            return None
        return value

    def register_external_value(self, unique_name, value):
        vid = value_name_identity(unique_name)
        self.value_provider_mediator.register(vid, value, vid.fingerprint if value is not None else None)
        # TODO: add a test!

        return value

    def get_external_value(self, unique_name):
        vid = value_name_identity(unique_name)
        return self.value_provider_mediator.resolve_value(vid)

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
