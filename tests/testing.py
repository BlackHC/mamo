from dataclasses import dataclass

from dumbo.internal import persisted_cache


@dataclass
class DummyPersistedCache(persisted_cache.DumboPersistedCache):
    external_cache_id: int
    vid_to_cached_value: dict

    def __init__(self, memory_only=False):
        self.external_cache_id = 0
        self.vid_to_cached_value = {}

    def cache_value(self, vid, value):
        return persisted_cache.DBCachedValue(value)

    def update(self, vid, value):
        self.vid_to_cached_value[vid] = self.cache_value(vid, value)

    def get_cached_value(self, vid):
        return self.vid_to_cached_value.get(vid)


@dataclass(frozen=True)
class Value:
    value: int