import dataclasses
from dataclasses import dataclass
from typing import Type

from dumbo.internal.fingerprints import Fingerprint, FingerprintDigest
from dumbo.internal.identities import ValueIdentity, value_name_identity, ValueFingerprintIdentity
from dumbo.internal.providers import ValueProvider
from dumbo.internal.staleness_registry import StalenessRegistry
from dumbo.internal.value_registries import ValueRegistry, WeakValueRegistry
from tests.testing import BoxedValue


@dataclass
class VVF:
    vid: ValueIdentity
    value: BoxedValue
    fingerprint: Fingerprint


class ValueProviderTests:
    value_provider: Type = None

    @staticmethod
    def create_vid(id: int = 0) -> ValueFingerprintIdentity:
        vid = value_name_identity(f"vid{id}")
        return vid

    def create_fingerprint(self, id) -> Fingerprint:
        return self.create_vid(id).fingerprint

    @staticmethod
    def create_value(id: int = 0):
        return BoxedValue(id)

    def create_vid_value_fingerprint(self, id: int = 0):
        return VVF(self.create_vid(id), self.create_value(id), self.create_fingerprint(id))

    @staticmethod
    def add_vvf(value_provider: ValueProvider, vvf: VVF):
        value_provider.add(vvf.vid, vvf.value, vvf.fingerprint)

    @staticmethod
    def assert_vvf_in_provider(value_provider: ValueProvider, vvf: VVF):
        assert value_provider.identify_value(vvf.value) == vvf.vid
        assert value_provider.fingerprint_value(vvf.value) == vvf.fingerprint
        assert value_provider.resolve_value(vvf.vid) == vvf.value
        assert value_provider.resolve_fingerprint(vvf.vid) == vvf.fingerprint
        assert value_provider.has_vid(vvf.vid)
        assert value_provider.has_value(vvf.value)

    @staticmethod
    def assert_vvf_missing(value_provider: ValueProvider, vvf: VVF):
        assert value_provider.identify_value(vvf.value) is None
        assert value_provider.fingerprint_value(vvf.value) is None
        assert value_provider.resolve_value(vvf.vid) is None
        assert value_provider.resolve_fingerprint(vvf.vid) is None
        assert not value_provider.has_vid(vvf.vid)
        assert not value_provider.has_value(vvf.value)

    @classmethod
    def create_value_provider(cls) -> ValueProvider:
        raise NotImplementedError()

    def test_add_and_getters(self):
        instance = self.create_value_provider()
        vvf = self.create_vid_value_fingerprint()

        self.assert_vvf_missing(instance, vvf)
        self.add_vvf(instance, vvf)
        self.assert_vvf_in_provider(instance, vvf)
        # And add a second time to make sure nothing changes.
        self.add_vvf(instance, vvf)
        self.assert_vvf_in_provider(instance, vvf)

    def test_update_value_works(self):
        instance = self.create_value_provider()
        vvf = self.create_vid_value_fingerprint(1)
        vvf2 = dataclasses.replace(vvf, value=self.create_value(2))

        self.add_vvf(instance, vvf)
        self.assert_vvf_in_provider(instance, vvf)
        self.add_vvf(instance, vvf2)
        self.assert_vvf_in_provider(instance, vvf2)

    def test_remove_vid(self):
        instance = self.create_value_provider()
        vvf = self.create_vid_value_fingerprint()

        instance.remove_vid(self.create_vid(1))
        self.assert_vvf_missing(instance, vvf)
        self.add_vvf(instance, vvf)
        instance.remove_vid(self.create_vid(2))
        self.assert_vvf_in_provider(instance, vvf)
        instance.remove_vid(vvf.vid)
        instance.remove_vid(self.create_vid(3))
        self.assert_vvf_missing(instance, vvf)

    def test_remove_value(self):
        instance = self.create_value_provider()
        vvf = self.create_vid_value_fingerprint()

        instance.remove_value(None)
        self.assert_vvf_missing(instance, vvf)
        self.add_vvf(instance, vvf)

        instance.remove_value(None)
        self.assert_vvf_in_provider(instance, vvf)
        instance.remove_value(vvf.value)
        self.assert_vvf_missing(instance, vvf)

        instance.remove_value(None)

    def test_get_vids(self):
        instance = self.create_value_provider()
        vvf = self.create_vid_value_fingerprint(1)
        vvf2 = self.create_vid_value_fingerprint(2)

        assert not instance.get_vids()
        self.add_vvf(instance, vvf)
        assert instance.get_vids() == {vvf.vid}
        self.add_vvf(instance, vvf2)
        assert instance.get_vids() == {vvf.vid, vvf2.vid}
        instance.remove_value(vvf.value)
        instance.remove_value(vvf2.value)
        assert not instance.get_vids()


class TestValueRegistry(ValueProviderTests):
    value_registry = ValueRegistry

    @classmethod
    def create_value_provider(cls) -> ValueRegistry:
        return cls.value_registry(StalenessRegistry())

    def test_staleness(self):
        instance = self.create_value_provider()
        vvf = self.create_vid_value_fingerprint()

        assert not instance.staleness_registry.is_stale(vvf.value)
        self.add_vvf(instance, vvf)
        assert not instance.staleness_registry.is_stale(vvf.value)
        instance.remove_vid(vvf.vid)
        assert instance.staleness_registry.is_stale(vvf.value)
        self.add_vvf(instance, vvf)
        assert not instance.staleness_registry.is_stale(vvf.value)


class TestWeakValueRegistry(TestValueRegistry):
    value_registry = WeakValueRegistry

    def test_weakness_works(self):
        instance = self.create_value_provider()
        vvf = self.create_vid_value_fingerprint()

        self.assert_vvf_missing(instance, vvf)
        self.add_vvf(instance, vvf)
        self.assert_vvf_in_provider(instance, vvf)

        del vvf
        assert not instance.get_vids()