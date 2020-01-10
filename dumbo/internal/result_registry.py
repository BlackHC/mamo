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
    online_registry: WeakValueRegistry
    persisted_store: PersistedStore

    def __init__(self, staleness_registry: StalenessRegistry, persisted_cache: PersistedStore):
        self.values = IdSet()
        self.online_registry = WeakValueRegistry(staleness_registry)

        self.persisted_store = persisted_cache

    def identify_value(self, value) -> ValueIdentity:
        return self.online_registry.identify_value(value)

    def fingerprint_value(self, value):
        return self.online_registry.fingerprint_value(value)

    def get_vids(self):
        return self.online_registry.get_vids()

    def flush(self):
        self.values.clear()

    def add(self, vid: ValueIdentity, value, fingerprint: Fingerprint):
        assert isinstance(vid, ComputedValueIdentity)
        assert value is not None

        existing_value = self.online_registry.resolve_value(vid)
        if existing_value is value:
            return

        if existing_value is not None:
            self.values.discard(existing_value)

        self.values.add(value)
        self.online_registry.add(vid, value, fingerprint)

        self.persisted_store.update(vid, AnnotatedValue(value, fingerprint))

    def remove_vid(self, vid: ValueIdentity):
        assert isinstance(vid, ComputedValueIdentity)

        value = self.online_registry.resolve_value(vid)
        if value is None:
            return

        self.values.discard(value)
        self.online_registry.remove_value(value)

        self.persisted_store.update(vid, None)

    def remove_value(self, value: object):
        if not self.has_value(value):
            return

        self.persisted_store.update(self.identify_value(value), None)
        self.values.discard(value)
        self.online_registry.remove_value(value)

    # TODO: remove this!! mainly tests need to be updated!
    def update(self, vid: ValueIdentity, annotated_value: Optional[AnnotatedValue]):
        if annotated_value is None:
            self.remove_vid(vid)
        else:
            self.add(vid, annotated_value.value, annotated_value.fingerprint)

    # TODO: rename to something that makes clear it might be very expensive!!
    def resolve_value(self, vid: ComputedValueIdentity):
        value = self.online_registry.resolve_value(vid)
        if value is None:
            annotated_value = self.persisted_store.get_stored_result(vid)
            if annotated_value is not None:
                value = annotated_value.value
                self.values.add(value)
                self.online_registry.add(vid, value, annotated_value.fingerprint)

        return value

    def resolve_fingerprint(self, vid: ComputedValueIdentity):
        fingerprint = self.online_registry.fingerprint_value(self.online_registry.resolve_value(vid))

        if fingerprint is None:
            cached_value = self.persisted_store.get_cached_value(vid)
            if cached_value is not None:
                fingerprint = cached_value.fingerprint

        return fingerprint

    def has_vid(self, vid):
        return self.online_registry.has_vid(vid) or self.persisted_store.has_vid(vid)

    def has_value(self, value):
        return self.online_registry.has_value(value)
