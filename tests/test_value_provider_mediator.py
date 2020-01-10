import dataclasses

import pytest

from dumbo.internal.fingerprints import ResultFingerprint
from dumbo.internal.identities import ValueCallIdentity, FunctionIdentity, ValueFingerprintIdentity, value_name_identity
from dumbo.internal.providers import ValueOracle, ValueProvider
from dumbo.internal.staleness_registry import StalenessRegistry
from dumbo.internal.value_provider_mediator import ValueProviderMediator
from dumbo.internal.value_registries import ValueRegistry
from tests.test_value_registries import ValueProviderTests, VVF
from tests.testing import DummyPersistedStore


class NullValueOracle(ValueOracle):
    def identify_value(self, value):
        return None

    def fingerprint_value(self, value):
        return None


class TestValueProviderMediatorWithNamedIdentities(ValueProviderTests):
    @staticmethod
    def create_vid(id: int = 0):
        vid = value_name_identity(f"test_fid{id}")
        return vid

    def create_fingerprint(self, id: int = 0):
        return self.create_vid(id).fingerprint

    @staticmethod
    def assert_vvf_missing(value_provider: ValueProvider, vvf: VVF):
        assert value_provider.identify_value(vvf.value) is None
        assert value_provider.fingerprint_value(vvf.value) is None
        assert value_provider.resolve_value(vvf.vid) is None

        if not isinstance(vvf.vid, ValueFingerprintIdentity):
            assert value_provider.resolve_fingerprint(vvf.vid) is None
        else:
            assert value_provider.resolve_fingerprint(vvf.vid) == vvf.fingerprint

        assert not value_provider.has_vid(vvf.vid)
        assert not value_provider.has_value(vvf.value)

    @staticmethod
    def create_value_provider() -> ValueProviderMediator:
        # Tt violates the "each call, different result" policy
        # TODO: add a custom exception type!
        staleness_registry = StalenessRegistry()
        value_provider_mediator = ValueProviderMediator()
        null_oracle = NullValueOracle()
        value_provider_mediator.init(null_oracle, null_oracle, ValueRegistry(staleness_registry),
                             ValueRegistry(staleness_registry))
        return value_provider_mediator

    def test_adding_value_twice_throws(self):
        instance = self.create_value_provider()
        vvf = self.create_vid_value_fingerprint(1)
        vvf2 = dataclasses.replace(vvf, vid=self.create_vid(2), fingerprint=self.create_fingerprint(2))

        self.add_vvf(instance, vvf)
        self.assert_vvf_in_provider(instance, vvf)

        with pytest.raises(AttributeError):
            self.add_vvf(instance, vvf2)


class TestValueProviderMediatorWithCalls(TestValueProviderMediatorWithNamedIdentities):
    @staticmethod
    def create_vid(id: int = 0):
        vid = ValueCallIdentity(FunctionIdentity(f"test_fid{id}"), (), frozenset())
        return vid

    @staticmethod
    def create_fingerprint(id: int = 0):
        return ResultFingerprint()
