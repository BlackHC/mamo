from dataclasses import dataclass
from types import FunctionType

from dumbo.internal.fingerprints import Fingerprint, FingerprintProvider, ResultFingerprint, FingerprintName
from dumbo.internal.id_set import IdSet, KeyIdMap
from dumbo.internal.weakref_utils import IdMapFinalizer, WeakIdSet, WrappedValueMutableMapping, WeakKeyIdMap, supports_weakrefs
from dumbo.internal.identities import ValueIdentity, value_name_identity, ComputedValueIdentity, IdentityProvider, FunctionIdentity
from dumbo.internal.annotated_value import AnnotatedValue
from dumbo.internal.persisted_cache import DumboPersistedCache
from typing import Dict, Optional, Any, Union, MutableMapping, Set, NoReturn
import weakref
from dumbo.internal.bimap import DictBimap, MappingBimap


class StalenessRegistry:
    # We need to keep track of unlinked values to be able to tell that they are stale now!
    stale_values: WeakIdSet[object]

    def __init__(self):
        super().__init__()
        self.stale_values = WeakIdSet()

    def mark_stale(self, value):
        self.stale_values.add(value)

    def mark_used(self, value):
        self.stale_values.discard(value)

    def is_stale(self, value):
        return value in self.stale_values


class IValueRegistry(IdentityProvider, FingerprintProvider):
    def resolve_value(self, vid: ValueIdentity) -> object:
        raise NotImplementedError()

    def resolve_fingerprint(self, vid: ValueIdentity) -> Fingerprint:
        raise NotImplementedError()

    def register(self, vid: ValueIdentity, value, fingerprint: Fingerprint) -> NoReturn:
        raise NotImplementedError()

    def invalidate(self, value: object) -> NoReturn:
        raise NotImplementedError()

    def has_vid(self, vid: ValueIdentity) -> bool:
        raise NotImplementedError()

    def has_value(self, value) -> bool:
        raise NotImplementedError()

    def get_vids(self) -> Set[ValueIdentity]:
        raise NotImplementedError()


@dataclass
class AbstractValueRegistry(IValueRegistry):
    vid_value_bimap: MappingBimap[ValueIdentity, object]
    value_to_fingerprint: MutableMapping[object, Fingerprint]
    staleness_registry: StalenessRegistry

    def identify_value(self, value) -> ValueIdentity:
        return self.vid_value_bimap.get_key(value)

    def fingerprint_value(self, value) -> Fingerprint:
        return self.value_to_fingerprint.get(value)

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
            self.value_to_fingerprint[value] = fingerprint
            self.staleness_registry.mark_used(value)

    def invalidate(self, value: object):
        self.staleness_registry.mark_stale(value)
        self.vid_value_bimap.del_value(value)
        del self.value_to_fingerprint[value]

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


@dataclass
class MainValueRegistry(IValueRegistry):
    results: IValueRegistry
    external_values: IValueRegistry

    def identify_value(self, value) -> ValueIdentity:
        return self.external_values.identify_value(value) or self.results.identify_value(value)

    def fingerprint_value(self, value) -> Fingerprint:
        return self.external_values.fingerprint_value(value) or self.results.fingerprint_value(value)

    def resolve_value(self, vid: ValueIdentity):
        if isinstance(vid, ComputedValueIdentity):
            return self.results.resolve_value(vid)
        return self.external_values.resolve_value(vid)

    def resolve_fingerprint(self, vid: ValueIdentity):
        if isinstance(vid, ComputedValueIdentity):
            return self.results.resolve_fingerprint(vid)
        return self.external_values.resolve_fingerprint(vid)

    def register(self, vid: ValueIdentity, value: object, fingerprint: Optional[Fingerprint]):
        if value is not None:
            existing_vid = self.identify_value(value)
            if existing_vid is not None and existing_vid != vid:
                raise AttributeError(
                    f"{vid} has same value as {existing_vid}!"
                    'We follow an "each computation, different result" policy.'
                    "This makes tracking possible."
                )

        # Vids are compartmentalized by value registry and thus we don't need any
        # additional error checking here.

        if isinstance(vid, ComputedValueIdentity):
            return self.results.register(vid, value, fingerprint)
        else:
            return self.external_values.register(vid, value, fingerprint)

    def invalidate(self, value: object):
        if self.external_values.has_value(value):
            self.external_values.invalidate(value)
        elif self.results.has_value(value):
            self.results.invalidate(value)

    def has_vid(self, vid: ValueIdentity):
        return self.external_values.has_vid(vid) or self.results.has_vid(vid)

    def has_value(self, value):
        return self.external_values.has_value(value) or self.external_values.has_value(value)

    def get_vids(self) -> Set[ValueIdentity]:
        vids = set()
        vids.update(self.external_values.get_vids())
        vids.update(self.results.get_vids())
        return vids


class OnlineLayer(IValueRegistry):
    values: IdSet
    result_registry: WeakValueRegistry
    persisted_cache: DumboPersistedCache

    def __init__(self, staleness_registry: StalenessRegistry, persisted_cache: DumboPersistedCache):
        self.values = IdSet()
        self.result_registry = WeakValueRegistry(staleness_registry)

        self.persisted_cache = persisted_cache

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

        self.persisted_cache.update(vid, annotated_value)

    # TODO: rename to something that makes clear it might be very expensive!!
    def resolve_value(self, vid: ComputedValueIdentity):
        value = self.result_registry.resolve_value(vid)
        if value is None:
            annotated_value = self.persisted_cache.get_stored_result(vid)
            if annotated_value is not None:
                value = annotated_value.value
                self.values.add(value)
                self.result_registry.register(vid, value, annotated_value.fingerprint)

        return value

    def resolve_fingerprint(self, vid: ComputedValueIdentity):
        fingerprint = self.result_registry.fingerprint_value(self.result_registry.resolve_value(vid))

        if fingerprint is None:
            cached_value = self.persisted_cache.get_cached_value(vid)
            if cached_value is not None:
                fingerprint = cached_value.fingerprint

        return fingerprint

    def has_vid(self, vid):
        return self.result_registry.has_vid(vid) is not None or self.persisted_cache.has_vid(vid)

    def has_value(self, value):
        return self.result_registry.has_value(value) is not None


# # TODO: big Q: does online cache only hold CIDs and external objects?
# # TODO: use weaksets!
# # TODO: repr method
# class DumboOnlineCache(FingerprintProvider):
#     persisted_cache: DumboPersistedCache
#
#     vid_to_value: _WeakValueDict
#     value_id_to_fingerprint: Dict[int, Fingerprint]
#     value_id_to_vid: Dict[int, ValueIdentity]
#     id_map_finalizer: IdMapFinalizer
#
#     tag_to_vid: DictBimap[str, ValueIdentity]
#
#     # We need to keep track of unlinked values to be able to tell that they are stale now!
#     stale_values: WeakIdSet
#
#     def __init__(self, persisted_cache):
#         self.persisted_cache = persisted_cache
#
#         self.vid_to_value = _WeakValueDict()
#         self.value_id_to_fingerprint = {}
#         self.value_id_to_vid = {}
#         self.id_map_finalizer = IdMapFinalizer()
#         self.tag_to_vid = DictBimap()
#         self.stale_values = WeakIdSet()
#
#     def fingerprint_value(self, value):
#         return self.value_id_to_fingerprint.get(id(value))
#
#     def has_vid(self, vid):
#         return vid in self.vid_to_value or self.persisted_cache.has_vid(vid)
#
#     def has_value(self, value):
#         return id(value) in self.value_id_to_vid
#
#     def get_stored_fingerprint(self, vid: ValueIdentity) -> Optional[Fingerprint]:
#         annotated_value = self.persisted_cache.get_cached_value(vid)
#
#         if annotated_value is not None:
#             return annotated_value.fingerprint
#         return None
#
#     def get_value(self, vid):
#         value = None
#
#         if vid in self.vid_to_value:
#             value = self.vid_to_value[vid]
#         else:
#             annotated_result = self.persisted_cache.get_stored_result(vid)
#             if annotated_result is not None:
#                 # Cache the stored_result in the online layer.
#                 value = annotated_result.value
#                 self.vid_to_value[vid] = value
#                 self.value_id_to_vid[id(value)] = vid
#                 self.value_id_to_fingerprint[id(value)] = annotated_result.fingerprint
#
#         return value
#
#     def get_vid(self, value):
#         return self.value_id_to_vid.get(id(value))
#
#     # TODO: this should call into the persisted cache! (not main!)
#     def get_vids(self):
#         return self.vid_to_value.keys()
#
#     # TODO: flush external?
#     def flush(self):
#         """Flush values from cache that are not weakref-counted."""
#         for vid in list(self.vid_to_value):
#             if not self.vid_to_value.is_weak_ref(vid):
#                 value = self.vid_to_value[vid]
#                 value_id = id(value)
#                 self.id_map_finalizer.release(value)
#                 del self.value_id_to_fingerprint[value_id]
#                 del self.value_id_to_vid[value_id]
#                 del self.vid_to_value[vid]
#
#     def _release_value(self, id_value):
#         vid = self.value_id_to_vid[id_value]
#         del self.value_id_to_vid[id_value]
#         del self.value_id_to_fingerprint[id_value]
#         del self.vid_to_value[vid]
#         self.tag_to_vid.del_value(vid)
#
#     def update(self, vid: ValueIdentity, annotated_value: Optional[AnnotatedValue]):
#         # This is a transactional function that first error-checks/validates and
#         # only then performs mutations.
#         # This can still fail to be atomic because of bugs
#         # but not because of invalid parameters.
#         value_id = id(annotated_value.value) if annotated_value is not None else None
#
#         # Validation checks:
#
#         # 1. If `vid` is already cached, don't trigger any events if we want to store the same value.
#         existing_value = None
#         if vid in self.vid_to_value:
#             existing_value = self.vid_to_value[vid]
#             # TODO: this keeps being buggy because of the annotated_value is None scenario.
#             if annotated_value is not None and existing_value is annotated_value.value:
#                 return
#
#         # 2. If `value` is already stored, it already has to be linked to the same `vid`.
#         existing_vid = self.value_id_to_vid.get(value_id) if value_id is not None else None
#         if existing_vid is not None:
#             # An early-out ought to have happened already above.
#             assert existing_vid is not vid
#
#             # ERROR: Value has already been linked to another vid.
#             raise AttributeError(
#                 f"{vid} has same value as {existing_vid}!"
#                 'We follow an "each computation, different result" policy.'
#                 "This makes tracking possible."
#             )
#
#         # Now: value is new (or we would have early-outed) and there might be an existing_value linked to vid.
#
#         # Perform mutations:
#         # Unlink existing value.
#         if existing_value is not None:
#             existing_value_id = id(existing_value)
#             del self.value_id_to_vid[existing_value_id]
#             del self.value_id_to_fingerprint[existing_value_id]
#             self.stale_values.add(existing_value)
#             self.id_map_finalizer.release(existing_value)
#
#         if annotated_value is not None:
#             self.id_map_finalizer.register(annotated_value.value, self._release_value)
#             self.vid_to_value[vid] = annotated_value.value
#             self.value_id_to_vid[value_id] = vid
#             self.value_id_to_fingerprint[value_id] = annotated_value.fingerprint
#         else:
#             del self.vid_to_value[vid]
#             self.tag_to_vid.del_value(vid)
#
#         # We only support caching computed values for now.
#         # Fingerprints/hashes can change and named values can be reloaded
#         # using initialization code.
#         if isinstance(vid, ComputedValueIdentity):
#             self.persisted_cache.update(vid, annotated_value)
#
#     def is_stale(self, value):
#         return value in self.stale_values
#
#     def tag(self, tag_name: str, vid: Optional[ValueIdentity]):
#         if vid is not None and vid not in self.vid_to_value:
#             raise ValueError(f"{vid} has not been cached!")
#
#         self.tag_to_vid.update(tag_name, vid)
#         # TODO: add tests for tagging external values (regression for this added if isinstance)
#         if vid is None or isinstance(vid, ComputedValueIdentity):
#             self.persisted_cache.tag(tag_name, vid)
#
#     def get_tag_value(self, tag_name: str):
#         tag_vid = self.tag_to_vid.get_value(tag_name)
#         if tag_vid is None:
#             tag_vid = self.persisted_cache.get_tag_vid(tag_name)
#         if tag_vid is None:
#             return None
#
#         return self.get_value(tag_vid)
