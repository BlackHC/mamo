import ast
import dataclasses
from typing import Optional, List

from functools import wraps

from mamo.internal.fingerprint_registry import FingerprintRegistry
from mamo.internal.fingerprints import Fingerprint, CellResultFingerprint, ResultFingerprint
from mamo.internal.identities import (
    ValueIdentity,
    value_name_identity,
    ComputedValueIdentity,
    ValueCallIdentity,
    ValueCellResultIdentity)
from mamo.internal.identity_registry import IdentityRegistry
from mamo.internal.function_registry import FunctionRegistry
from mamo.internal.module_extension import MODULE_EXTENSIONS
from mamo.internal.result_metadata import ResultMetadata
from mamo.internal.result_registry import ResultRegistry
from mamo.internal.stopwatch_context import StopwatchContext
from mamo.internal.value_provider_mediator import ValueProviderMediator
from mamo.internal.value_registries import ValueRegistry
from mamo.internal.staleness_registry import StalenessRegistry
from mamo.internal.persisted_store import PersistedStore

from mamo.internal import default_module_extension

# Install the default module extension.
MODULE_EXTENSIONS.set_default_extension(default_module_extension.DefaultModuleExtension())


class ReExecutionPolicy:
    def __call__(
            self,
            mamo: "Mamo",
            vid: ComputedValueIdentity,
            fingerprint: ResultFingerprint,
            stored_fingerprint: Optional[ResultFingerprint],
    ):
        return True


def execute_decision_only_missing(
        mamo: "Mamo", vid: ComputedValueIdentity, fingerprint: Fingerprint, stored_fingerprint: Optional[Fingerprint]
):
    return False


def execute_decision_stale(max_depth):
    def decider(
            mamo: "Mamo", vid: ComputedValueIdentity, fingerprint: ResultFingerprint,
            stored_fingerprint: Optional[ResultFingerprint]
    ):
        if fingerprint != stored_fingerprint:
            return True
        return mamo.is_stale_vid(vid, depth=max_depth)

    return decider


class Mamo:
    fingerprint_registry: FingerprintRegistry
    identity_registry: IdentityRegistry
    staleness_registry: StalenessRegistry
    function_registry: FunctionRegistry

    value_provider_mediator: ValueProviderMediator
    external_value_registry: ValueRegistry
    result_registry: ResultRegistry

    persisted_store: PersistedStore

    re_execution_policy: ReExecutionPolicy

    _call_duration_stack: List
    _nomamo_call_duration_stack: List

    def __init__(self, persisted_store, deep_fingerprint_source_prefix: Optional[str],
                 re_execution_policy: Optional[ReExecutionPolicy]):
        self.persisted_store = persisted_store

        self.value_provider_mediator = ValueProviderMediator()

        self.staleness_registry = StalenessRegistry()
        self.external_value_registry = ValueRegistry(self.staleness_registry)
        self.result_registry = ResultRegistry(self.staleness_registry, persisted_store)

        self.function_registry = FunctionRegistry()
        self.fingerprint_registry = FingerprintRegistry(deep_fingerprint_source_prefix, self.value_provider_mediator,
                                                        self.value_provider_mediator, self.function_registry)
        self.identity_registry = IdentityRegistry(self.value_provider_mediator)

        self.value_provider_mediator.init(self.identity_registry, self.fingerprint_registry, self.result_registry,
                                          self.external_value_registry)

        self.re_execution_policy = re_execution_policy or execute_decision_stale(-1)

        self._call_duration_stack = [0.0]
        self._nomamo_call_duration_stack = [0.0]

    def swap_persisted_store(self, new_persisted_store):
        self.persisted_store.close()
        self.persisted_store = new_persisted_store
        self.result_registry.persisted_store = new_persisted_store

    @property
    def deep_fingerprint_source_prefix(self):
        return self.fingerprint_registry.deep_fingerprint_source_prefix

    # TODO: remove this property again (only used by tests!)

    @deep_fingerprint_source_prefix.setter
    def deep_fingerprint_source_prefix(self, value):
        self.fingerprint_registry.deep_fingerprint_source_prefix = value

    def _get_value(self, vid: ValueIdentity):
        return self.value_provider_mediator.resolve_value(vid)

    def _get_vid(self, value: object):
        return self.value_provider_mediator.identify_value(value)

    def get_value_identities(self, persisted=False):
        # TODO: optimize to always create a new set?
        vids = self.value_provider_mediator.get_vids()
        if persisted:
            vids.update(self.persisted_store.get_vids())
        return vids

    def flush_cache(self):
        self.result_registry.flush()

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

        fingerprint = self.fingerprint_registry.fingerprint_computed_value(vid)
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

    def is_cached_call(self, func, args, kwargs):
        fid = self.function_registry.identify_function(func)
        vid = self.identity_registry.identify_call(fid, args, kwargs)

        return self.value_provider_mediator.has_vid(vid)

    def forget_call(self, func, args, kwargs):
        fid = self.function_registry.identify_function(func)
        vid = self.identity_registry.identify_call(fid, args, kwargs)

        self.value_provider_mediator.remove_vid(vid)

    def forget(self, value):
        if not self.value_provider_mediator.has_value(value):
            # TODO: throw or log
            return
        self.value_provider_mediator.remove_value(value)

    def get_metadata_call(self, func, args, kwargs) -> Optional[ResultMetadata]:
        fid = self.function_registry.identify_function(func)
        vid = self.identity_registry.identify_call(fid, args, kwargs)

        metadata = self.persisted_store.get_result_metadata(vid)
        if not metadata:
            return None
        return dataclasses.replace(metadata)

    def get_metadata(self, value) -> Optional[ResultMetadata]:
        vid = self.value_provider_mediator.identify_value(value)
        metadata = self.persisted_store.get_result_metadata(vid)

        if not metadata:
            return None
        return dataclasses.replace(metadata)

    def _shall_execute(self, vid: ComputedValueIdentity, fingerprint: ResultFingerprint):
        # TODO: could directly ask persisted_cache
        stored_fingerprint = mamo.result_registry.resolve_fingerprint(vid)
        return stored_fingerprint is None or self.re_execution_policy(self, vid, fingerprint, stored_fingerprint)

    @staticmethod
    def wrap_function(func):
        @wraps(func)
        def wrapped_func(*args, **kwargs):
            with StopwatchContext() as total_stopwatch:
                nonlocal fid

                # If mamo was not initialized before, we might still have to set fid.
                if fid is None:
                    # Just initialize it with defaults.
                    if mamo is None:
                        # TODO: maybe log?
                        init_mamo()

                    fid = mamo.function_registry.identify_function(func)

                vid = mamo.identity_registry.identify_call(fid, args, kwargs)

                call_fingerprint = mamo.fingerprint_registry.fingerprint_call(func, args, kwargs)
                result_metadata = mamo.persisted_store.get_result_metadata(vid)

                if mamo._shall_execute(vid, call_fingerprint):
                    mamo._call_duration_stack.append(0.)
                    mamo._nomamo_call_duration_stack.append(0.)
                    with StopwatchContext() as call_stopwatch:
                        result = func(*args, **kwargs)
                    wrapped_result = MODULE_EXTENSIONS.wrap_return_value(result)
                    mamo.value_provider_mediator.add(vid, wrapped_result, call_fingerprint)

                    result_metadata = mamo.persisted_store.get_result_metadata(vid)
                    result_metadata.call_duration = call_stopwatch.elapsed_time
                    result_metadata.subcall_duration = mamo._call_duration_stack.pop()
                    result_metadata.estimated_nomamo_call_duration = result_metadata.call_duration - result_metadata.subcall_duration + mamo._nomamo_call_duration_stack.pop()
                else:
                    wrapped_result = mamo._get_value(vid)
                    if wrapped_result is None:
                        # log?
                        raise RuntimeError(f"Couldn't find cached result for {vid}!")

                    result_metadata.num_cache_hits += 1

            result_metadata.total_durations += total_stopwatch.elapsed_time
            mamo._call_duration_stack[-1] += total_stopwatch.elapsed_time
            mamo._nomamo_call_duration_stack[-1] += result_metadata.estimated_nomamo_call_duration
            return wrapped_result

        wrapped_func.mamo_unwrapped_func = func
        wrapped_func.is_stale = lambda *args, **kwargs: mamo.is_stale_call(func, args, kwargs)
        wrapped_func.is_cached = lambda *args, **kwargs: mamo.is_cached_call(func, args, kwargs)
        wrapped_func.forget = lambda *args, **kwargs: mamo.forget_call(func, args, kwargs)
        wrapped_func.get_metadata = lambda *args, **kwargs: mamo.get_metadata_call(func, args, kwargs)
        wrapped_func.get_tag_name = lambda *args, **kwargs: mamo.get_tag_name_call(func, args, kwargs)

        # This method is a static method, so that mamo does not need to be initialized.
        fid = None
        if mamo is not None:
            fid = mamo.function_registry.identify_function(func)

        return wrapped_func

    def run_cell(self, name: Optional[str], cell_code: str, user_ns: dict):
        # TODO: wrap in a function and execute, so we need explicit globals for stores?
        function_module = ast.parse("def cell_function():\n  pass")
        cell_module = ast.parse(cell_code)
        function_module.body[0].body = cell_module.body
        compiled_function = compile(function_module, "<code>", "exec")

        local_ns = {}
        exec(compiled_function, user_ns, local_ns)
        cell_function = local_ns["cell_function"]

        cell_id = self.function_registry.identify_cell(name, cell_function)
        cell_fingerprint = self.fingerprint_registry.fingerprint_cell(cell_function)

        outputs = cell_fingerprint.outputs

        result_vids = {name: self.identity_registry.identify_cell_result(cell_id, name) for name in outputs}
        result_fingerprints = {
            name: self.fingerprint_registry.fingerprint_cell_result(cell_fingerprint, name) for name in outputs
        }

        # TODO: this adds some staleness overhead but not sure how to handle composites atm.
        if any(mamo._shall_execute(result_vids[name], result_fingerprints[name]) for name in outputs):
            cell_function()

            # Retrieve stores.
            wrapped_results = {name: MODULE_EXTENSIONS.wrap_return_value(user_ns[name]) for name in outputs}
            user_ns.update(wrapped_results)

            for name in outputs:
                mamo.value_provider_mediator.add(result_vids[name],
                                                  user_ns[name], result_fingerprints[name])
        else:
            for name in outputs:
                vid = result_vids[name]
                cached_result = mamo._get_value(vid)
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

        self.persisted_store.tag(tag_name, vid)

    def get_tag_name_call(self, func, args, kwargs) -> Optional[str]:
        fid = self.function_registry.identify_function(func)
        vid = self.identity_registry.identify_call(fid, args, kwargs)

        return self.persisted_store.get_tag_name(vid)

    def get_tag_name(self, value) -> Optional[str]:
        vid = self._get_vid(value)
        if not vid:
            return None
        return self.persisted_store.get_tag_name(vid)

    def get_tag_value(self, tag_name):
        # TODO: might have to expose has_tag etc?
        vid = self.persisted_store.get_tag_vid(tag_name)
        if vid is None:
            # TODO: log instead
            # raise ValueError(f"{tag_name} has not been registered previously!")
            return None
        value = self.value_provider_mediator.resolve_value(vid)
        if value is None:
            # TODO: log instead!
            # raise ValueError(f"{vid} for {tag_name} is not available anymore!")
            return None
        return value

    def register_external_value(self, unique_name, value):
        vid = value_name_identity(unique_name)
        if value is None:
            self.value_provider_mediator.remove_vid(vid)
        else:
            self.value_provider_mediator.add(vid, value, vid.fingerprint)
        # TODO: add a test!

        return value

    def get_external_value(self, unique_name):
        vid = value_name_identity(unique_name)
        return self.value_provider_mediator.resolve_value(vid)

    # noinspection PyTypeChecker
    def testing_close(self):
        self.persisted_store.close()
        self.identity_registry = None
        self.fingerprint_registry = None
        self.value_provider_mediator = None
        import gc
        gc.collect()


mamo: Optional[Mamo] = None


def init_mamo(
        memory_only=True,
        path: Optional[str] = None,
        externally_cached_path: Optional[str] = None,
        # By default, we don't use deep fingerprints except in the main module/jupyter notebooks.
        deep_fingerprint_source_prefix: Optional[str] = None,
        re_execution_policy: Optional[ReExecutionPolicy] = None
):
    global mamo
    assert mamo is None

    new_persisted_store = (
        PersistedStore.from_memory()
        if memory_only
        else PersistedStore.from_file(path, externally_cached_path)
    )
    mamo = Mamo(new_persisted_store, deep_fingerprint_source_prefix, re_execution_policy)


# TODO: add tests!
# TODO: This is a hack because it breaks metadata!
def swap_storage(
    memory_only=True,
    path: Optional[str] = None,
    externally_cached_path: Optional[str] = None
):
    assert mamo is not None

    new_persisted_store = (
        PersistedStore.from_memory()
        if memory_only
        else PersistedStore.from_file(path, externally_cached_path)
    )

    mamo.swap_persisted_store(new_persisted_store)
