from dataclasses import dataclass
from typing import Optional

from _pytest.fixtures import fixture

import dumbo
from dumbo.internal import persisted_cache, main
from dumbo.internal.cached_values import DBCachedValue
from dumbo.internal.identities import ValueIdentity
from dumbo.internal.annotated_value import AnnotatedValue


@dataclass
class DummyPersistedCache(persisted_cache.DumboPersistedCache):
    external_cache_id: int
    vid_to_cached_value: dict
    tag_to_vid: dict

    def __init__(self):
        self.external_cache_id = 0
        self.vid_to_cached_value = {}
        self.tag_to_vid = {}

    def try_create_cached_value(self, vid, stored_result):
        return AnnotatedValue(DBCachedValue(stored_result), stored_result.fingerprint)

    def update(self, vid, value):
        self.vid_to_cached_value[vid] = self.try_create_cached_value(vid, value) if value is not None else None

    def get_cached_value(self, vid):
        return self.vid_to_cached_value.get(vid)

    def tag(self, tag_name: str, vid: ValueIdentity):
        self.tag_to_vid[tag_name] = vid

    def get_tag_vid(self, tag_name) -> Optional[ValueIdentity]:
        return self.tag_to_vid.get(tag_name)


@dataclass(frozen=True)
class BoxedValue:
    value: int


@fixture
def dumbo_fixture():
    if main.dumbo is not None:
        main.dumbo.testing_close()
        main.dumbo = None

    main.init_dumbo()

    yield main.dumbo

    main.dumbo.testing_close()
    main.dumbo = None
