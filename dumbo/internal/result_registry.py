from dumbo.internal.fingerprints import Fingerprint
from dumbo.internal.common.id_set import IdSet
from dumbo.internal.providers import ValueProvider
from dumbo.internal.staleness_registry import StalenessRegistry
from dumbo.internal.value_registries import WeakValueRegistry
from dumbo.internal.identities import ValueIdentity, ComputedValueIdentity
from dumbo.internal.annotated_value import AnnotatedValue
from dumbo.internal.persisted_store import PersistedStore
from typing import Optional


class ResultRegistry(ValueProvider):
    values: IdSet
    result_registry: WeakValueRegistry
    persisted_store: PersistedStore

    def __init__(self, staleness_registry: StalenessRegistry, persisted_cache: PersistedStore):
        self.values = IdSet()
        self.result_registry = WeakValueRegistry(staleness_registry)

        self.persisted_store = persisted_cache

    def identify_value(self, value) -> ValueIdentity:
        return self.result_registry.identify_value(value)

    def fingerprint_value(self, value):
        return self.result_registry.fingerprint_value(value)

    def get_vids(self):
        return self.result_registry.get_vids()

    def flush(self):
        self.values.clear()

    def register(self, vid: ComputedValueIdentity, value: object, fingerprint: Fingerprint):
        self.update(vid, AnnotatedValue(value, fingerprint))

    def invalidate(self, value):
        vid = self.identify_value(value)
        if vid is not None:
            self.update(vid, None)

    # TODO: _update?
    # TODO: wanna support vid=None, value given?
    def update(self, vid: ValueIdentity, annotated_value: Optional[AnnotatedValue]):
        assert isinstance(vid, ComputedValueIdentity)

        existing_value = self.result_registry.resolve_value(vid)
        if annotated_value is None:
            if existing_value is None:
                return
        elif existing_value is annotated_value.value:
            return

        if existing_value is not None:
            self.values.discard(existing_value)

        if annotated_value is not None:
            self.values.add(annotated_value.value)
            self.result_registry.register(vid, annotated_value.value, annotated_value.fingerprint)
        else:
            self.result_registry.invalidate(existing_value)

        self.persisted_store.update(vid, annotated_value)

    # TODO: rename to something that makes clear it might be very expensive!!
    def resolve_value(self, vid: ComputedValueIdentity):
        value = self.result_registry.resolve_value(vid)
        if value is None:
            annotated_value = self.persisted_store.get_stored_result(vid)
            if annotated_value is not None:
                value = annotated_value.value
                self.values.add(value)
                self.result_registry.register(vid, value, annotated_value.fingerprint)

        return value

    def resolve_fingerprint(self, vid: ComputedValueIdentity):
        fingerprint = self.result_registry.fingerprint_value(self.result_registry.resolve_value(vid))

        if fingerprint is None:
            cached_value = self.persisted_store.get_cached_value(vid)
            if cached_value is not None:
                fingerprint = cached_value.fingerprint

        return fingerprint

    def has_vid(self, vid):
        return self.result_registry.has_vid(vid) or self.persisted_store.has_vid(vid)

    def has_value(self, value):
        return self.result_registry.has_value(value)
