from dataclasses import dataclass
from typing import Optional

from _pytest.fixtures import fixture

from dumbo.internal import persisted_store, main
from dumbo.internal.annotated_value import AnnotatedValue
from dumbo.internal.cached_values import DBPickledValue
from dumbo.internal.identities import ValueIdentity


@dataclass
class DummyPersistedStore(persisted_store.PersistedStore):
    external_cache_id: int
    vid_to_cached_value: dict
    vid_to_fingerprint: dict
    tag_to_vid: dict

    # noinspection PyMissingConstructor
    def __init__(self):
        self.external_cache_id = 0
        self.vid_to_cached_value = {}
        self.vid_to_fingerprint = {}
        self.tag_to_vid = {}

    def try_create_cached_value(self, vid, value):
        return DBPickledValue(value)

    def add(self, vid, value: object, fingerprint):
        self.vid_to_cached_value[vid] = self.try_create_cached_value(vid, value)
        self.vid_to_fingerprint[vid] = fingerprint

    def remove_vid(self, vid):
        if vid in self.vid_to_cached_value:
            del self.vid_to_cached_value[vid]
            del self.vid_to_fingerprint[vid]

    def update(self, vid, value: AnnotatedValue):
        if value is None:
            self.remove_vid(vid)
        else:
            self.add(vid, value.value, value.fingerprint)

    def get_cached_value(self, vid):
        value = self.vid_to_cached_value.get(vid)
        if not value:
            return None
        fingerprint = self.vid_to_fingerprint.get[vid]
        return AnnotatedValue(value, fingerprint)

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
