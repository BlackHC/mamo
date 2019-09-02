from dataclasses import dataclass
from typing import Optional

import dumbo.internal.cached_values
from dumbo.internal import persisted_cache
from dumbo.internal.identities import ValueIdentity


@dataclass
class DummyPersistedCache(persisted_cache.DumboPersistedCache):
    external_cache_id: int
    vid_to_cached_value: dict
    tag_to_vid: dict

    def __init__(self):
        self.external_cache_id = 0
        self.vid_to_cached_value = {}
        self.tag_to_vid = {}

    def try_create_cached_value(self, vid, value):
        return dumbo.internal.cached_values.DBCachedValue(value)

    def update(self, vid, value):
        self.vid_to_cached_value[vid] = self.try_create_cached_value(vid, value)

    def get_cached_value(self, vid):
        return self.vid_to_cached_value.get(vid)

    def tag(self, tag_name: str, vid: ValueIdentity):
        self.tag_to_vid[tag_name] = vid

    def get_tag_vid(self, tag_name) -> Optional[ValueIdentity]:
        return self.tag_to_vid.get(tag_name)


@dataclass(frozen=True)
class Value:
    value: int