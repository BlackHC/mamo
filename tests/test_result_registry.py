import dataclasses

from mamo.internal.fingerprints import ResultFingerprint
from mamo.internal.identities import ValueCallIdentity, FunctionIdentity
from mamo.internal.providers import ValueProvider
from mamo.internal.result_registry import ResultRegistry
from mamo.internal.staleness_registry import StalenessRegistry
from tests.test_value_registries import VVF, ValueProviderTests
from tests.testing import DummyPersistedStore, BoxedValue


@dataclasses.dataclass
class DummyResultFingerprint(ResultFingerprint):
    id: int


class TestResultRegistry(ValueProviderTests):
    @staticmethod
    def create_vid(id: int = 0):
        vid = ValueCallIdentity(FunctionIdentity(f"test_fid{id}"), (), frozenset())
        return vid

    @staticmethod
    def create_fingerprint(id):
        return DummyResultFingerprint(id)

    @staticmethod
    def create_value_provider() -> ResultRegistry:
        persisted_store = DummyPersistedStore()
        result_registry = ResultRegistry(StalenessRegistry(), persisted_store)
        return result_registry

    def test_uses_persisted_cache(self):
        instance = self.create_value_provider()
        vvf = self.create_vid_value_fingerprint(0)
        value = self.create_value(0)
        vid = vvf.vid
        fingerprint = vvf.fingerprint

        assert vvf == vvf

        self.assert_vvf_missing(instance, vvf)
        self.add_vvf(instance, vvf)

        del vvf
        instance.flush()

        assert instance.has_vid(vid)
        # TODO: this is weird tbh. But cannot separate between online and persisted vids otherwise?
        # Maybe be explicit in Mamo?
        assert not instance.get_vids()

        assert instance.persisted_store.get_fingerprint(vid) == fingerprint
        assert instance.persisted_store.load_value(vid) == value

        assert instance.resolve_fingerprint(vid) == fingerprint

        # This will load the value again.
        loaded_value = instance.resolve_value(vid)
        assert loaded_value == value
        self.assert_vvf_in_provider(instance, VVF(vid, loaded_value, fingerprint))
        assert instance.get_vids() == {vid}
