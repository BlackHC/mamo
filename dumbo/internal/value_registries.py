import weakref
from dataclasses import dataclass
from typing import MutableMapping, Set

from dumbo.internal.bimap import MappingBimap
from dumbo.internal.fingerprints import Fingerprint
from dumbo.internal.id_set import KeyIdMap
from dumbo.internal.identities import ValueIdentity, ComputedValueIdentity
from dumbo.internal.providers import ValueProvider
from dumbo.internal.staleness_registry import StalenessRegistry
from dumbo.internal.weakref_utils import WeakKeyIdMap


@dataclass
class AbstractValueRegistry(ValueProvider):
    vid_value_bimap: MappingBimap[ValueIdentity, object]
    value_fingerprint_map: MutableMapping[object, Fingerprint]
    staleness_registry: StalenessRegistry

    def identify_value(self, value) -> ValueIdentity:
        return self.vid_value_bimap.get_key(value)

    def fingerprint_value(self, value) -> Fingerprint:
        return self.value_fingerprint_map.get(value)

    def resolve_value(self, vid: ValueIdentity):
        return self.vid_value_bimap.get_value(vid)

    def resolve_fingerprint(self, vid: ValueIdentity):
        return self.fingerprint_value(self.resolve_value(vid))

    def register(self, vid: ComputedValueIdentity, value: object, fingerprint: Fingerprint):
        if vid in self.vid_value_bimap:
            existing_value = self.vid_value_bimap.get_value(vid)
            self.staleness_registry.mark_stale(existing_value)

        self.vid_value_bimap.update(vid, value)
        if value is not None:
            self.value_fingerprint_map[value] = fingerprint
            self.staleness_registry.mark_used(value)

    def invalidate(self, value: object):
        self.staleness_registry.mark_stale(value)
        self.vid_value_bimap.del_value(value)
        del self.value_fingerprint_map[value]

    def has_vid(self, vid: ValueIdentity):
        return vid in self.vid_value_bimap

    def has_value(self, value):
        return self.vid_value_bimap.has_value(value)

    def get_vids(self) -> Set[ValueIdentity]:
        return set(self.vid_value_bimap.get_keys())


class ValueRegistry(AbstractValueRegistry):
    def __init__(self, staleness_registry: StalenessRegistry):
        vid_value_bimap = MappingBimap({}, KeyIdMap())
        value_to_fingerprint = KeyIdMap()
        super().__init__(vid_value_bimap, value_to_fingerprint, staleness_registry)


class WeakValueRegistry(AbstractValueRegistry):
    def __init__(self, staleness_registry: StalenessRegistry):
        vid_value_bimap = MappingBimap(weakref.WeakValueDictionary(), WeakKeyIdMap())
        value_to_fingerprint = WeakKeyIdMap()
        super().__init__(vid_value_bimap, value_to_fingerprint, staleness_registry)