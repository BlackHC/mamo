import dumbo.internal.persisted_cache
import pytest

from dumbo.internal.fingerprints import ResultFingerprint
from dumbo.internal.identities import value_name_identity, ValueCallIdentity, FunctionIdentity
from dumbo.internal.annotated_value import AnnotatedValue, AnnotatedValue
from dumbo.internal.online_cache import OnlineLayer
from dumbo.internal.value_provider_mediator import ValueProviderMediator
from dumbo.internal.value_registries import ValueRegistry
from dumbo.internal.staleness_registry import StalenessRegistry

from .testing import DummyPersistedCache, BoxedValue

# TODO: gotta check fingerprints, too!


def create_call_vid(id: int = 0):
    vid = ValueCallIdentity(FunctionIdentity(f"test_fid{id}"), frozenset(), frozenset())
    return vid


def test_doc_initial_update_works():
    persisted_cache = DummyPersistedCache()
    online_cache = OnlineLayer(StalenessRegistry(), persisted_cache)

    # TODO: add register_external_value to online_cache

    vid = create_call_vid()
    fingerprint = ResultFingerprint()

    value = AnnotatedValue(BoxedValue(5), fingerprint)
    online_cache.update(vid, value)

    assert online_cache.resolve_value(vid) is value.value
    assert online_cache.identify_value(value.value) == vid


def test_doc_updating_value_works():
    persisted_cache = DummyPersistedCache()
    online_cache = OnlineLayer(StalenessRegistry(), persisted_cache)

    vid = create_call_vid()
    fingerprint = ResultFingerprint()
    value1 = AnnotatedValue(BoxedValue(5), fingerprint)
    online_cache.update(vid, value1)

    assert online_cache.resolve_value(vid) is value1.value
    assert online_cache.identify_value(value1.value) == vid

    value2 = AnnotatedValue(BoxedValue(7), fingerprint)

    online_cache.update(vid, value2)
    assert online_cache.resolve_value(vid) is value2.value
    assert online_cache.identify_value(value2.value) == vid
    assert online_cache.identify_value(value1.value) is None

def test_doc_updating_same_value_throws():
    # Tt violates the "each call, different result" policy
    # TODO: add a custom exception type!
    persisted_cache = DummyPersistedCache()
    staleness_registry = StalenessRegistry()
    online_cache = ValueProviderMediator(ValueRegistry(staleness_registry), ValueRegistry(staleness_registry))

    vid = create_call_vid(1)
    fingerprint = ResultFingerprint()
    value = BoxedValue(5)
    online_cache.register(vid, value, fingerprint)

    assert online_cache.resolve_value(vid) is value
    assert online_cache.identify_value(value) == vid

    vid2 = create_call_vid(2)
    with pytest.raises(AttributeError):
        online_cache.register(vid2, value, fingerprint)


def test_doc_updating_none_works():
    persisted_cache = DummyPersistedCache()
    online_cache = OnlineLayer(StalenessRegistry(), persisted_cache)

    vid = create_call_vid()
    fingerprint = ResultFingerprint()
    value = AnnotatedValue(BoxedValue(5), fingerprint)
    online_cache.update(vid, value)

    assert online_cache.resolve_value(vid) is value.value
    assert online_cache.identify_value(value.value) == vid

    online_cache.update(vid, None)

    assert online_cache.resolve_value(vid) is None
    assert online_cache.identify_value(value.value) is None


def test_doc_updating_none_works_cid():
    persisted_cache = DummyPersistedCache()
    online_cache = OnlineLayer(StalenessRegistry(), persisted_cache)

    vid = create_call_vid()
    value = AnnotatedValue(BoxedValue(5), None)
    online_cache.update(vid, value)

    assert online_cache.resolve_value(vid) is value.value
    assert online_cache.identify_value(value.value) == vid

    online_cache.update(vid, None)

    assert online_cache.resolve_value(vid) is None
    assert online_cache.identify_value(value.value) is None

# TODO: renable!
# def test_doc_tagging_works():
#     persisted_cache = DummyPersistedCache()
#     online_cache = OnlineLayer(StalenessRegistry(), persisted_cache)
#
#     vid = ValueCallIdentity(None, None, None
#     value = AnnotatedValue(BoxedValue(5), vid.fingerprint)
#     tag_name = "quack"
#
#     online_cache.update(vid, value)
#     online_cache.tag(tag_name, vid)
#
#     assert online_cache.resolve_value(vid) is value.value
#     assert online_cache.identify_value(value.value) == vid
#     assert online_cache.get_tag_value(tag_name) is value.value


def test_doc_get_vids_works():
    persisted_cache = DummyPersistedCache()
    online_cache = OnlineLayer(StalenessRegistry(), persisted_cache)

    vid = create_call_vid()
    fingerprint = ResultFingerprint()
    value = AnnotatedValue(BoxedValue(5), fingerprint)

    online_cache.update(vid, value)

    assert online_cache.get_vids() == {vid}
