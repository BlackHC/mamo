from dumbo.internal.identities import ValueCIDIdentity, ValueIdentity
from dumbo.internal.persisted_cache import DumboPersistedCache
from typing import Dict, Any
from dumbo.internal.bimap import DictBimap


# TODO: to repr method
class DumboOnlineCache:
    persisted_cache: DumboPersistedCache
    vid_to_value: Dict[ValueIdentity, Any]
    id_value_to_vid: Dict[int, ValueIdentity]
    tag_to_vid: DictBimap[str, ValueIdentity]

    def __init__(self, persisted_cache):
        self.persisted_cache = persisted_cache

        self.vid_to_value = {}
        self.id_value_to_vid = {}
        self.tag_to_vid = DictBimap()

    def has_value(self, value):
        return id(value) in self.id_value_to_vid

    def get_value(self, vid):
        if vid in self.vid_to_value:
            return self.vid_to_value[vid]

        value = self.persisted_cache.get_value(vid)
        if value is not None:
            # Cache the value in the online layer.
            self.vid_to_value[vid] = value
            self.id_value_to_vid[id(value)] = vid

        return value

    def get_vid(self, value):
        return self.id_value_to_vid.get(id(value))

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

        existing_vid = self.id_value_to_vid.get(id(value)) if value is not None else None
        if existing_vid is not None:
            if existing_vid is not vid:
                # ERROR: Value has already been linked to another vid.
                raise AttributeError(
                    f"{vid} has same value as {existing_vid}!"
                    "We follow an \"each computation, different result\" policy."
                    "This makes tracking possible."
                )

        # Now perform mutations:
        # Unlink existing value.
        if existing_value is not None:
            del self.id_value_to_vid[id(existing_value)]

        if existing_vid is None:
            self.id_value_to_vid[id(value)] = vid

        if value is not None:
            self.vid_to_value[vid] = value
        else:
            del self.vid_to_value[vid]
            self.tag_to_vid.del_value(vid)

        # We only support caching computed values for now.
        # Fingerprints/hashes can change and named values can be reloaded
        # using initialization code.
        if isinstance(vid, ValueCIDIdentity):
            self.persisted_cache.update(vid, value)

    def tag(self, vid, tag_name):
        if vid is not None and vid not in self.vid_to_value:
            raise ValueError(f"{vid} has not been cached!")

        self.tag_to_vid.update(vid, tag_name)
        self.persisted_cache.tag(vid, tag_name)

    def get_tag_value(self, tag_name):
        tag_vid = self.tag_to_vid.get_value(tag_name)
        if tag_vid is None:
            tag_vid = self.persisted_cache.get_tag_vid(tag_name)
        if tag_vid is None:
            return None

        return self.get_value(tag_vid)
