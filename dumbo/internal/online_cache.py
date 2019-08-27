from dumbo.internal.identities import ValueCIDIdentity, ValueIdentity
from dumbo.internal.persisted_cache import DumboPersistedCache
from typing import Dict, Any


# TODO: to repr method
class DumboOnlineCache:
    persisted_cache: DumboPersistedCache
    vid_to_value: Dict[ValueIdentity, Any]
    value_to_vid: Dict[int, ValueIdentity]

    def __init__(self, persisted_cache):
        self.vid_to_value = {}
        self.value_to_vid = {}
        self.persisted_cache = persisted_cache

    def has_value(self, value):
        return id(value) in self.value_to_vid

    def get_value(self, vid):
        if vid in self.vid_to_value:
            return self.vid_to_value[vid]

        value = self.persisted_cache.get_cached_value(vid)
        if value is not None:
            # Cache the value in the online layer.
            self.vid_to_value[vid] = value
            self.value_to_vid[id(value)] = vid

        return value

    def get_vid(self, value):
        return self.value_to_vid.get(id(value))

    def update(self, vid: ValueIdentity, value):
        # This is a transactional function that first error-checks/validates and
        # only then performs mutations.
        # This can still fail to be atomic because of bugs
        # but not because of invalid parameters.

        # Validation checks:
        existing_value = None
        if vid in self.vid_to_value:
            existing_value = self.vid_to_value[vid]
            if existing_value is value:
                return

        existing_vid = self.value_to_vid.get(id(value))
        if existing_vid is not None:
            if existing_vid is not vid:
                # ERROR: Value has already been linked to another vid.
                # TODO: support handlers to create views/proxies on existing results.
                raise AttributeError(
                    f"{vid} has same value as {existing_vid}!"
                    "We follow a \"each computation, different result\" policy."
                    "This makes tracking possible."
                )

        # Now perform mutations:
        # Unlink existing value.
        if existing_value is not None:
            del self.value_to_vid[id(existing_value)]

        if existing_vid is None:
            self.value_to_vid[id(value)] = vid

        self.vid_to_value[vid] = value

        # We only support caching computed values for now.
        # Fingerprints/hashes can change and named values can be reloaded
        # using initialization code.
        if isinstance(vid, ValueCIDIdentity):
            self.persisted_cache.update(vid, value)
