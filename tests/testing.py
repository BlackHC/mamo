from dataclasses import dataclass
from typing import Optional, Dict

from _pytest.fixtures import fixture

from mamo.internal import persisted_store, main
from mamo.internal.cached_values import CachedValue
from mamo.internal.db_stored_value import DBPickledValue
from mamo.internal.fingerprints import Fingerprint
from mamo.internal.identities import ValueIdentity
from mamo.internal.persisted_store import CacheOperationResult
from mamo.internal.result_metadata import ResultMetadata


@dataclass
class DummyPersistedStore(persisted_store.PersistedStore):
    external_cache_id: int
    vid_to_cached_value: Dict[ValueIdentity, CachedValue]
    vid_to_fingerprint: Dict[ValueIdentity, Fingerprint]
    vid_to_metadata: Dict[ValueIdentity, ResultMetadata]
    tag_to_vid: dict

    # noinspection PyMissingConstructor
    def __init__(self):
        self.external_cache_id = 0
        self.vid_to_cached_value = {}
        self.vid_to_metadata = {}
        self.vid_to_fingerprint = {}
        self.tag_to_vid = {}

    def get_vids(self):
        return set(self.vid_to_cached_value.keys())

    def has_vid(self, vid):
        return vid in self.vid_to_cached_value

    def try_create_cached_value(self, vid, value):
        return CacheOperationResult(DBPickledValue.cache_value(value), 0, 0, 0)

    def add(self, vid, value: object, fingerprint):
        result = self.try_create_cached_value(vid, value)
        self.vid_to_cached_value[vid] = result.cached_value
        self.vid_to_fingerprint[vid] = fingerprint
        self.vid_to_metadata[vid] = ResultMetadata(0, 0, 0.)

    def remove_vid(self, vid):
        if vid in self.vid_to_cached_value:
            del self.vid_to_cached_value[vid]
            del self.vid_to_fingerprint[vid]
            del self.vid_to_metadata[vid]

    def get_fingerprint(self, vid):
        return self.vid_to_fingerprint.get(vid)

    def get_cached_value(self, vid):
        return self.vid_to_cached_value.get(vid)

    def load_value(self, vid: ValueIdentity):
        cached_value = self.vid_to_cached_value.get(vid)
        if cached_value:
            value = cached_value.load()
            return value
        return None

    def get_result_metadata(self, vid: ValueIdentity) -> ResultMetadata:
        return self.vid_to_metadata.get(vid)

    def tag(self, tag_name: str, vid: ValueIdentity):
        self.tag_to_vid[tag_name] = vid

    def get_tag_vid(self, tag_name) -> Optional[ValueIdentity]:
        return self.tag_to_vid.get(tag_name)


@dataclass(frozen=True)
class BoxedValue:
    value: int


@fixture
def mamo_fixture():
    if main.mamo is not None:
        main.mamo.testing_close()
        main.mamo = None

    main.init_mamo()

    yield main.mamo

    main.mamo.testing_close()
    main.mamo = None
