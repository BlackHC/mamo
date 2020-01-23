from mamo.internal.delayed_interruption_context import delayed_interruption
from mamo.internal.fingerprints import Fingerprint, ResultFingerprint
from mamo.internal.common.id_set import IdSet
from mamo.internal.providers import ValueProvider
from mamo.internal.staleness_registry import StalenessRegistry
from mamo.internal.value_registries import WeakValueRegistry
from mamo.internal.identities import ValueIdentity, ComputedValueIdentity
from mamo.internal.persisted_store import PersistedStore


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

    def flush_value(self, value):
        self.values.remove(value)

    def add(self, vid: ComputedValueIdentity, value, fingerprint: ResultFingerprint):
        assert isinstance(vid, ComputedValueIdentity)
        assert isinstance(fingerprint, ResultFingerprint)
        assert value is not None

        existing_value = self.online_registry.resolve_value(vid)
        if existing_value is value:
            return

        self.persisted_store.add(vid, value, fingerprint)

        with delayed_interruption():
            if existing_value is not None:
                self.values.discard(existing_value)

            self.online_registry.add(vid, value, fingerprint)
            self.values.add(value)

    def remove_vid(self, vid: ValueIdentity):
        assert isinstance(vid, ComputedValueIdentity)

        value = self.online_registry.resolve_value(vid)

        with delayed_interruption():
            if value is not None:
                self.values.discard(value)
                self.online_registry.remove_value(value)

            self.persisted_store.remove_vid(vid)

    @delayed_interruption()
    def remove_value(self, value: object):
        if not self.has_value(value):
            return

        self.persisted_store.remove_vid(self.identify_value(value))
        self.values.discard(value)
        self.online_registry.remove_value(value)

    # TODO: rename to something that makes clear it might be very expensive!!
    def resolve_value(self, vid: ComputedValueIdentity):
        value = self.online_registry.resolve_value(vid)
        if value is None and self.persisted_store.has_vid(vid):
            value = self.persisted_store.load_value(vid)
            fingerprint = self.persisted_store.get_fingerprint(vid)
            self.values.add(value)
            self.online_registry.add(vid, value, fingerprint)

        return value

    def resolve_fingerprint(self, vid: ComputedValueIdentity):
        fingerprint = self.online_registry.fingerprint_value(self.online_registry.resolve_value(vid))

        if fingerprint is None:
            fingerprint = self.persisted_store.get_fingerprint(vid)

        return fingerprint

    def has_vid(self, vid):
        return self.online_registry.has_vid(vid) or self.persisted_store.has_vid(vid)

    def has_value(self, value):
        return self.online_registry.has_value(value)
