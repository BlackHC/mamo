from dumbo.internal.fingerprints import Fingerprint, FingerprintProvider
from dumbo.internal.weakref_utils import IdMapFinalizer, WeakIdSet, WrappedValueMutableMapping, supports_weakrefs
from dumbo.internal.identities import ValueCallIdentity, ValueIdentity, ComputedValueIdentity, ValueFingerprintIdentity
from dumbo.internal.annotated_value import AnnotatedValue, AnnotatedValue
from dumbo.internal.persisted_cache import DumboPersistedCache
from typing import Dict, Optional, Any, MutableMapping, Union
import weakref
from dumbo.internal.bimap import DictBimap


# TODO: the weakref stuff is still broken :'-(
class _WeakValueDict(WrappedValueMutableMapping[ValueIdentity, Any, Union[weakref.ref, Any]]):
    def is_weak_ref(self, k: ValueIdentity):
        return isinstance(self.data.get(k), weakref.ref)

    def _value_to_store(self, v):
        #return weakref.ref(v) if supports_weakrefs(v) else lambda: v
        return v

    def _store_to_value(self, v: weakref.ref):
        return v


# TODO: big Q: does online cache only hold CIDs and external objects?
# TODO: use weaksets!
# TODO: repr method
class DumboOnlineCache(FingerprintProvider):
    persisted_cache: DumboPersistedCache

    vid_to_value: _WeakValueDict
    value_id_to_fingerprint: Dict[int, Fingerprint]
    value_id_to_vid: Dict[int, ValueIdentity]
    id_map_finalizer: IdMapFinalizer

    tag_to_vid: DictBimap[str, ValueIdentity]

    # We need to keep track of unlinked values to be able to tell that they are stale now!
    stale_values: WeakIdSet

    def __init__(self, persisted_cache):
        self.persisted_cache = persisted_cache

        self.vid_to_value = _WeakValueDict()
        self.value_id_to_fingerprint = {}
        self.value_id_to_vid = {}
        self.id_map_finalizer = IdMapFinalizer()
        self.tag_to_vid = DictBimap()
        self.stale_values = WeakIdSet()

    def fingerprint_value(self, value):
        return self.value_id_to_fingerprint.get(id(value))

    def has_vid(self, vid):
        return vid in self.vid_to_value or self.persisted_cache.has_vid(vid)

    def has_value(self, value):
        return id(value) in self.value_id_to_vid

    def get_stored_fingerprint(self, vid: ValueIdentity) -> Optional[Fingerprint]:
        annotated_value = self.persisted_cache.get_cached_value(vid)

        if annotated_value is not None:
            return annotated_value.fingerprint
        return None

    def get_value(self, vid):
        value = None

        if vid in self.vid_to_value:
            value = self.vid_to_value[vid]
        else:
            annotated_result = self.persisted_cache.get_stored_result(vid)
            if annotated_result is not None:
                # Cache the stored_result in the online layer.
                value = annotated_result.value
                self.vid_to_value[vid] = value
                self.value_id_to_vid[id(value)] = vid
                self.value_id_to_fingerprint[id(value)] = annotated_result.fingerprint

        return value

    def get_vid(self, value):
        return self.value_id_to_vid.get(id(value))

    # TODO: this should call into the persisted cache! (not main!)
    def get_vids(self):
        return self.vid_to_value.keys()

    # TODO: flush external?
    def flush(self):
        """Flush values from cache that are not weakref-counted."""
        for vid in list(self.vid_to_value):
            if not self.vid_to_value.is_weak_ref(vid):
                value = self.vid_to_value[vid]
                value_id = id(value)
                self.id_map_finalizer.release(value)
                del self.value_id_to_fingerprint[value_id]
                del self.value_id_to_vid[value_id]
                del self.vid_to_value[vid]

    def _release_value(self, id_value):
        vid = self.value_id_to_vid[id_value]
        del self.value_id_to_vid[id_value]
        del self.value_id_to_fingerprint[id_value]
        del self.vid_to_value[vid]
        self.tag_to_vid.del_value(vid)

    def update(self, vid: ValueIdentity, annotated_value: Optional[AnnotatedValue]):
        # This is a transactional function that first error-checks/validates and
        # only then performs mutations.
        # This can still fail to be atomic because of bugs
        # but not because of invalid parameters.
        value_id = id(annotated_value.value) if annotated_value is not None else None

        # Validation checks:

        # 1. If `vid` is already cached, don't trigger any events if we want to store the same value.
        existing_value = None
        if vid in self.vid_to_value:
            existing_value = self.vid_to_value[vid]
            # TODO: this keeps being buggy because of the annotated_value is None scenario.
            if annotated_value is not None and existing_value is annotated_value.value:
                return

        # 2. If `value` is already stored, it already has to be linked to the same `vid`.
        existing_vid = self.value_id_to_vid.get(value_id) if value_id is not None else None
        if existing_vid is not None:
            # An early-out ought to have happened already above.
            assert existing_vid is not vid

            # ERROR: Value has already been linked to another vid.
            raise AttributeError(
                f"{vid} has same value as {existing_vid}!"
                'We follow an "each computation, different result" policy.'
                "This makes tracking possible."
            )

        # Now: value is new (or we would have early-outed) and there might be an existing_value linked to vid.

        # Perform mutations:
        # Unlink existing value.
        if existing_value is not None:
            existing_value_id = id(existing_value)
            del self.value_id_to_vid[existing_value_id]
            del self.value_id_to_fingerprint[existing_value_id]
            self.stale_values.add(existing_value)
            self.id_map_finalizer.release(existing_value)

        if annotated_value is not None:
            self.id_map_finalizer.register(annotated_value.value, self._release_value)
            self.vid_to_value[vid] = annotated_value.value
            self.value_id_to_vid[value_id] = vid
            self.value_id_to_fingerprint[value_id] = annotated_value.fingerprint
        else:
            del self.vid_to_value[vid]
            self.tag_to_vid.del_value(vid)

        # We only support caching computed values for now.
        # Fingerprints/hashes can change and named values can be reloaded
        # using initialization code.
        if isinstance(vid, ComputedValueIdentity):
            self.persisted_cache.update(vid, annotated_value)

    def is_stale(self, value):
        return value in self.stale_values

    def tag(self, tag_name: str, vid: Optional[ValueIdentity]):
        if vid is not None and vid not in self.vid_to_value:
            raise ValueError(f"{vid} has not been cached!")

        self.tag_to_vid.update(tag_name, vid)
        # TODO: add tests for tagging external values (regression for this added if isinstance)
        if vid is None or isinstance(vid, ComputedValueIdentity):
            self.persisted_cache.tag(tag_name, vid)

    def get_tag_value(self, tag_name: str):
        tag_vid = self.tag_to_vid.get_value(tag_name)
        if tag_vid is None:
            tag_vid = self.persisted_cache.get_tag_vid(tag_name)
        if tag_vid is None:
            return None

        return self.get_value(tag_vid)
