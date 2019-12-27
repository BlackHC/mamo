from dumbo.internal.fingerprints import Fingerprint
from dumbo.internal.weakref_utils import IdMapFinalizer
from dumbo.internal.identities import ValueCIDIdentity, ValueIdentity, StoredValue, StoredResult
from dumbo.internal.persisted_cache import DumboPersistedCache
from typing import Dict, Optional, Set
from dumbo.internal.bimap import DictBimap


# TODO: big Q: does online cache only hold CIDs and external objects?
# TODO: use weaksets!
# TODO: to repr method
class DumboOnlineCache:
    persisted_cache: DumboPersistedCache

    vid_to_value: Dict[ValueIdentity, StoredValue]
    value_id_to_vid: Dict[int, ValueIdentity]
    id_map_finalizer: IdMapFinalizer
    tag_to_vid: DictBimap[str, ValueIdentity]
    # We need to keep track of unlinked values to be able to tell that they are stale now!
    # TODO: use a weakset!
    stale_values: Set[int]

    def __init__(self, persisted_cache):
        self.persisted_cache = persisted_cache

        self.vid_to_value = {}
        self.value_id_to_vid = {}
        self.id_map_finalizer = IdMapFinalizer()
        self.tag_to_vid = DictBimap()
        self.stale_values = set()

    def has_vid(self, vid):
        return vid in self.vid_to_value or self.persisted_cache.has_vid(vid)

    def has_value(self, value):
        return id(value) in self.value_id_to_vid

    def get_fingerprint_from_vid(self, vid: Optional[ValueIdentity]) -> Optional[Fingerprint]:
        if vid is None:
            return None

        if vid in self.vid_to_value:
            stored_value = self.vid_to_value[vid]
        else:
            stored_value = self.persisted_cache.get_cached_value(vid)

        if stored_value is not None:
            return stored_value.fingerprint
        return None

    def get_stored_value(self, vid):
        if vid in self.vid_to_value:
            return self.vid_to_value[vid]

        stored_result = self.persisted_cache.get_stored_result(vid)
        if stored_result is not None:
            # Cache the stored_result in the online layer.
            self.vid_to_value[vid] = stored_result
            self.value_id_to_vid[id(stored_result.value)] = vid

        return stored_result

    def get_vid(self, value):
        return self.value_id_to_vid.get(id(value))

    def get_vids(self):
        return self.vid_to_value.keys()

    def flush(self):
        self.vid_to_value.clear()
        # TODO: might want to flush this separately (because it might use less memory)
        self.value_id_to_vid.clear()

    def _release_value(self, id_value):
        vid = self.value_id_to_vid[id_value]
        del self.value_id_to_vid[id_value]
        del self.vid_to_value[vid]
        self.tag_to_vid.del_value(vid)

    def update(self, vid: ValueIdentity, stored_value: Optional[StoredValue]):
        # This is a transactional function that first error-checks/validates and
        # only then performs mutations.
        # This can still fail to be atomic because of bugs
        # but not because of invalid parameters.

        # Validation checks:
        existing_value = None
        if vid in self.vid_to_value:
            existing_value = self.vid_to_value[vid]
            if existing_value is stored_value:
                return

        existing_vid = self.value_id_to_vid.get(id(stored_value.value)) if stored_value is not None else None
        if existing_vid is not None:
            if existing_vid is not vid:
                # is not is very strict (vs !=) but that's okay.

                # ERROR: Value has already been linked to another vid.
                raise AttributeError(
                    f"{vid} has same value as {existing_vid}!"
                    'We follow an "each computation, different result" policy.'
                    "This makes tracking possible."
                )

        # Now perform mutations:
        # Unlink existing value.
        if existing_value is not None:
            id_existing_value = id(existing_value.value)
            del self.value_id_to_vid[id_existing_value]
            self.stale_values.add(id_existing_value)
            self.id_map_finalizer.release(existing_value.value)

        if stored_value is not None:
            self.vid_to_value[vid] = stored_value
            self.id_map_finalizer.register(stored_value.value, self._release_value)

            if existing_vid is None:
                self.value_id_to_vid[id(stored_value.value)] = vid
        else:
            del self.vid_to_value[vid]
            self.tag_to_vid.del_value(vid)

        # We only support caching computed values for now.
        # Fingerprints/hashes can change and named values can be reloaded
        # using initialization code.
        if isinstance(vid, ValueCIDIdentity):
            assert stored_value is None or isinstance(stored_value, StoredResult)
            self.persisted_cache.update(vid, stored_value)

    def is_stale(self, value):
        return id(value) in self.stale_values

    def tag(self, tag_name: str, vid: Optional[ValueIdentity]):
        if vid is not None and vid not in self.vid_to_value:
            raise ValueError(f"{vid} has not been cached!")

        self.tag_to_vid.update(tag_name, vid)
        # TODO: this breaks if vid is not stored in persisted_cache because it is not a value call identity!
        self.persisted_cache.tag(tag_name, vid)

    def get_tag_stored_value(self, tag_name: str):
        tag_vid = self.tag_to_vid.get_value(tag_name)
        if tag_vid is None:
            tag_vid = self.persisted_cache.get_tag_vid(tag_name)
        if tag_vid is None:
            return None

        return self.get_stored_value(tag_vid)
