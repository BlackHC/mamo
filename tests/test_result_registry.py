import pytest

from dumbo.internal.annotated_value import AnnotatedValue
from dumbo.internal.fingerprints import ResultFingerprint
from dumbo.internal.identities import ValueCallIdentity, FunctionIdentity
from dumbo.internal.providers import ValueOracle
from dumbo.internal.result_registry import ResultRegistry
from dumbo.internal.staleness_registry import StalenessRegistry
from dumbo.internal.value_provider_mediator import ValueProviderMediator
from dumbo.internal.value_registries import ValueRegistry
from .testing import DummyPersistedStore, BoxedValue


# TODO: gotta check fingerprints, too!


def create_call_vid(id: int = 0):
    vid = ValueCallIdentity(FunctionIdentity(f"test_fid{id}"), (), frozenset())
    return vid


def test_doc_initial_update_works():
    persisted_store = DummyPersistedStore()
    result_registry = ResultRegistry(StalenessRegistry(), persisted_store)

    # TODO: add register_external_value to result_registry

    vid = create_call_vid()
    fingerprint = ResultFingerprint()

    value = AnnotatedValue(BoxedValue(5), fingerprint)
    result_registry.update(vid, value)

    assert result_registry.resolve_value(vid) is value.value
    assert result_registry.identify_value(value.value) == vid


def test_doc_updating_value_works():
    persisted_store = DummyPersistedStore()
    result_registry = ResultRegistry(StalenessRegistry(), persisted_store)

    vid = create_call_vid()
    fingerprint = ResultFingerprint()
    value1 = AnnotatedValue(BoxedValue(5), fingerprint)
    result_registry.update(vid, value1)

    assert result_registry.resolve_value(vid) is value1.value
    assert result_registry.identify_value(value1.value) == vid

    value2 = AnnotatedValue(BoxedValue(7), fingerprint)

    result_registry.update(vid, value2)
    assert result_registry.resolve_value(vid) is value2.value
    assert result_registry.identify_value(value2.value) == vid
    assert result_registry.identify_value(value1.value) is None


class NullValueOracle(ValueOracle):
    def identify_value(self, value):
        return None

    def fingerprint_value(self, value):
        return None


def test_doc_updating_same_value_throws():
    # Tt violates the "each call, different result" policy
    # TODO: add a custom exception type!
    persisted_store = DummyPersistedStore()
    staleness_registry = StalenessRegistry()
    result_registry = ValueProviderMediator()
    null_oracle = NullValueOracle()
    result_registry.init(null_oracle, null_oracle, ValueRegistry(staleness_registry), ValueRegistry(staleness_registry))

    vid = create_call_vid(1)
    fingerprint = ResultFingerprint()
    value = BoxedValue(5)
    result_registry.register(vid, value, fingerprint)

    assert result_registry.resolve_value(vid) is value
    assert result_registry.identify_value(value) == vid

    vid2 = create_call_vid(2)
    with pytest.raises(AttributeError):
        result_registry.register(vid2, value, fingerprint)


def test_doc_updating_none_works():
    persisted_store = DummyPersistedStore()
    result_registry = ResultRegistry(StalenessRegistry(), persisted_store)

    vid = create_call_vid()
    fingerprint = ResultFingerprint()
    value = AnnotatedValue(BoxedValue(5), fingerprint)
    result_registry.update(vid, value)

    assert result_registry.resolve_value(vid) is value.value
    assert result_registry.identify_value(value.value) == vid

    result_registry.update(vid, None)

    assert result_registry.resolve_value(vid) is None
    assert result_registry.identify_value(value.value) is None


def test_doc_updating_none_works_cid():
    persisted_store = DummyPersistedStore()
    result_registry = ResultRegistry(StalenessRegistry(), persisted_store)

    vid = create_call_vid()
    value = AnnotatedValue(BoxedValue(5), None)
    result_registry.update(vid, value)

    assert result_registry.resolve_value(vid) is value.value
    assert result_registry.identify_value(value.value) == vid

    result_registry.update(vid, None)

    assert result_registry.resolve_value(vid) is None
    assert result_registry.identify_value(value.value) is None

# TODO: renable!
# def test_doc_tagging_works():
#     persisted_store = DummyPersistedStore()
#     result_registry = ResultRegistry(StalenessRegistry(), persisted_store)
#
#     vid = ValueCallIdentity(None, None, None
#     value = AnnotatedValue(BoxedValue(5), vid.fingerprint)
#     tag_name = "quack"
#
#     result_registry.update(vid, value)
#     result_registry.tag(tag_name, vid)
#
#     assert result_registry.resolve_value(vid) is value.value
#     assert result_registry.identify_value(value.value) == vid
#     assert result_registry.get_tag_value(tag_name) is value.value


def test_doc_get_vids_works():
    persisted_store = DummyPersistedStore()
    result_registry = ResultRegistry(StalenessRegistry(), persisted_store)

    vid = create_call_vid()
    fingerprint = ResultFingerprint()
    value = AnnotatedValue(BoxedValue(5), fingerprint)

    result_registry.update(vid, value)

    assert result_registry.get_vids() == {vid}
